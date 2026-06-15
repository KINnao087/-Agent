from __future__ import annotations

import contextvars
import json
import hashlib
import shutil
import threading
from dataclasses import asdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.domain.contracts.compare import build_summary, compare_basic_info
from core.domain.contracts.models import ContractBasicInfo
from core.domain.contracts.integrity_models import ContractPageText
from core.domain.reviews import ReviewStepRecord
from core.infrastructure.contracts.basic_info_extractor import extract_contract_basic_info
from core.infrastructure.contracts.authenticity_review import review_contract_authenticity
from core.infrastructure.contracts.integrity_review import (
    review_contract_seal_integrity,
    review_contract_text_integrity,
)
from core.infrastructure.reviews import (
    FileReviewStore,
    build_material_fingerprint,
    fingerprint_page_set,
    is_step_current,
)
from core.infrastructure.text import (
    build_linearized_document,
    normalize_document_images,
    parse_path_to_json_list,
    write_linearized_outputs,
    linearize_ocr_page,
)
from core.infrastructure.vision.seal import (
    detect_seal_candidates,
    review_cross_page_seal_images,
)

ReviewOperation = Callable[[], dict[str, Any]]
REQUIRED_REVIEW_STEPS = (
    "check_basic_info",
    "check_text_integrity",
    "check_contract_seals",
    "check_cross_page_seal",
    "check_contract_authenticity",
)


def _hash_json(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _classify_result(step_name: str, result: dict[str, Any]) -> str:
    if step_name == "check_basic_info":
        if result.get("review_status") != "completed":
            return "not_executed"
        return (
            "risk"
            if (result.get("summary") or {}).get("mismatched_fields", 0)
            else "passed"
        )
    if step_name == "check_text_integrity":
        statuses = {
            (result.get("contract_continuity") or {}).get("status"),
            (result.get("contract_completeness") or {}).get("status"),
            (result.get("replacement_page") or {}).get("status"),
            (result.get("contract_clarity") or {}).get("status"),
        }
        if statuses & {"discontinuous", "incomplete", "suspected", "unclear"}:
            return "risk"
        return "unknown" if "unknown" in statuses or None in statuses else "passed"
    if step_name == "check_contract_seals":
        parties = [
            result.get("seller_seal") or {},
            result.get("buyer_seal") or {},
        ]
        if any(
            party.get("present") is False
            or party.get("status") in {"missing", "damaged"}
            or (party.get("forgery_risk") or {}).get("risk_level") in {"medium", "high"}
            for party in parties
        ):
            return "risk"
        if any(
            party.get("present") is None
            or party.get("status") in {"unknown", "unclear"}
            for party in parties
        ):
            return "unknown"
        return "passed"
    if step_name == "check_cross_page_seal":
        if result.get("status") in {"missing", "incomplete"}:
            return "risk"
        if result.get("status") in {"unknown", "unclear", None}:
            return "unknown"
        return "passed"
    if step_name == "check_contract_authenticity":
        if result.get("conclusion") in {"validity_risk", "likely_invalid"}:
            return "risk"
        if result.get("conclusion") != "likely_valid":
            return "unknown"
        return "passed"
    return "passed"


def _render_report_markdown(report: dict[str, Any]) -> str:
    labels = {
        "passed": "已通过",
        "risk": "存在风险",
        "unknown": "无法确认",
        "not_executed": "未执行",
        "execution_failed": "执行失败",
    }
    lines = [
        "# 合同审核报告",
        "",
        f"- 审核任务：`{report['review_id']}`",
        f"- 综合状态：{labels.get(report['overall_status'], report['overall_status'])}",
        "",
        "## 专项结果",
        "",
    ]
    for name, section in report["sections"].items():
        lines.extend(
            [
                f"### {name}",
                "",
                f"状态：{labels.get(section['status'], section['status'])}",
                "",
                "```json",
                json.dumps(section.get("result"), ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def _copy_pages(paths: list[Path], target_dir: Path) -> list[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for index, source in enumerate(paths, start=1):
        target = target_dir / f"page-{index:04d}.png"
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        copied.append(target)
    return copied


class ContractReviewService:
    def __init__(
        self,
        *,
        store: FileReviewStore | None = None,
        normalize_images: Callable[..., list[Path]] = normalize_document_images,
        load_ocr_pages: Callable[[str | Path | None], list[dict]] = parse_path_to_json_list,
        extract_basic_info: Callable[[str], ContractBasicInfo] = extract_contract_basic_info,
        review_text_integrity: Callable[..., Any] = review_contract_text_integrity,
        detect_seals: Callable[..., list[Any]] = detect_seal_candidates,
        review_seals: Callable[..., Any] = review_contract_seal_integrity,
        review_cross_page_seal: Callable[..., Any] = review_cross_page_seal_images,
        review_authenticity: Callable[..., dict[str, Any]] = review_contract_authenticity,
        versions: dict[str, dict[str, str]] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        self.store = store or FileReviewStore()
        self.normalize_images = normalize_images
        self.load_ocr_pages = load_ocr_pages
        self.extract_basic_info = extract_basic_info
        self.review_text_integrity = review_text_integrity
        self.detect_seals = detect_seals
        self.review_seals = review_seals
        self.review_cross_page_seal = review_cross_page_seal
        self.review_authenticity = review_authenticity
        self.versions = versions or {}
        self._cancel_event = cancel_event

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event is not None and self._cancel_event.is_set()

    def _check_cancelled(self) -> None:
        if self.is_cancelled:
            raise RuntimeError("审核任务已被取消")

    def _versions_for(self, step_name: str) -> dict[str, str]:
        return self.versions.get(step_name, {})

    def _report_source_fingerprint(self, manifest: Any) -> str:
        sources = {}
        for name, record in manifest.steps.items():
            if name in {"prepare_contract", "write_review_report"}:
                continue
            result = None
            if record.result_path:
                result_path = self.store.review_dir(manifest.review_id) / record.result_path
                if result_path.exists():
                    result = self.store.read_result(
                        manifest.review_id,
                        record.result_path,
                    )
            sources[name] = {
                "record": record.model_dump(),
                "required_versions": self._versions_for(name),
                "result": result,
            }
        return _hash_json(sources)

    def _required_versions(
        self,
        step_name: str,
        manifest: Any,
    ) -> dict[str, str]:
        versions = dict(self._versions_for(step_name))
        if step_name == "write_review_report":
            versions["source_results"] = self._report_source_fingerprint(manifest)
        return versions

    def _normalize_for_identity(
        self,
        path: str | None,
        role: str,
    ) -> list[Path]:
        if not path:
            return []
        source_key = hashlib.sha256(
            str(Path(path).expanduser().resolve(strict=False)).encode("utf-8")
        ).hexdigest()[:16]
        cache_dir = self.store.root / "_material_cache" / role / source_key
        return [
            Path(item)
            for item in self.normalize_images(path, output_dir=cache_dir)
        ]

    @staticmethod
    def _prepared_artifacts_exist(manifest: Any) -> bool:
        required = {
            "ocr_payload",
            "contract_text",
            "attachments_text",
            "invoice_text",
        }
        return required <= manifest.artifacts.keys() and all(
            Path(manifest.artifacts[name]).exists()
            for name in required
        )

    def _material_identity(
        self,
        contract_path: str,
        attachments_path: str = "",
        invoice_path: str = "",
        platform_basic_info: dict[str, Any] | None = None,
    ) -> tuple[list[Path], list[Path], list[Path], str, str]:
        contract_pages = self._normalize_for_identity(contract_path, "contract")
        if not contract_pages:
            raise ValueError("no contract pages found in input")
        attachment_pages = self._normalize_for_identity(attachments_path, "attachments")
        invoice_pages = self._normalize_for_identity(invoice_path, "invoice")
        contract_fingerprint = fingerprint_page_set(contract_pages)
        material_fingerprint = build_material_fingerprint(
            contract_fingerprint=contract_fingerprint,
            attachment_paths=attachment_pages,
            invoice_paths=invoice_pages,
            platform_data=platform_basic_info,
        )
        return (
            contract_pages,
            attachment_pages,
            invoice_pages,
            contract_fingerprint,
            material_fingerprint,
        )

    def find_contract_review(
        self,
        contract_path: str,
        attachments_path: str = "",
        invoice_path: str = "",
        platform_basic_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        *_, material_fingerprint = self._material_identity(
            contract_path,
            attachments_path,
            invoice_path,
            platform_basic_info,
        )
        manifest = self.store.find_by_material(material_fingerprint)
        if not manifest:
            return {"found": False, "material_fingerprint": material_fingerprint}
        status = self.get_review_status(manifest.review_id)
        return {
            "found": True,
            "review_id": manifest.review_id,
            "material_fingerprint": material_fingerprint,
            "steps": status["steps"],
            "missing_steps": status["missing_steps"],
            "stale_steps": status["stale_steps"],
            "ready_for_report": status["ready_for_report"],
        }

    def prepare_contract(
        self,
        contract_path: str,
        attachments_path: str = "",
        invoice_path: str = "",
        platform_basic_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        (
            contract_pages,
            attachment_pages,
            invoice_pages,
            contract_fingerprint,
            material_fingerprint,
        ) = self._material_identity(
            contract_path,
            attachments_path,
            invoice_path,
            platform_basic_info,
        )
        manifest = self.store.create_or_load(
            contract_fingerprint=contract_fingerprint,
            material_fingerprint=material_fingerprint,
            inputs={
                "contract_path": contract_path,
                "attachments_path": attachments_path,
                "invoice_path": invoice_path,
                "platform_basic_info": platform_basic_info,
            },
        )
        versions = self._versions_for("prepare_contract")
        record = manifest.steps.get("prepare_contract")
        if (
            is_step_current(record, versions)
            and self._prepared_artifacts_exist(manifest)
        ):
            return {
                "review_id": manifest.review_id,
                "cached": True,
                "artifacts": manifest.artifacts,
            }

        manifest.steps["prepare_contract"] = ReviewStepRecord(
            status="running",
            versions=versions,
        )
        self.store.save(manifest)
        try:
            review_dir = self.store.review_dir(manifest.review_id)
            normalized = {
                "contract": _copy_pages(
                    contract_pages,
                    review_dir / "normalized" / "contract",
                ),
                "attachments": _copy_pages(
                    attachment_pages,
                    review_dir / "normalized" / "attachments",
                ),
                "invoice": _copy_pages(
                    invoice_pages,
                    review_dir / "normalized" / "invoice",
                ),
            }
            ocr_payload = {
                "input_path": contract_path,
                "contract": self.load_ocr_pages(
                    review_dir / "normalized" / "contract"
                ),
                "attachments": self.load_ocr_pages(
                    review_dir / "normalized" / "attachments"
                )
                if normalized["attachments"]
                else [],
                "invoice": self.load_ocr_pages(
                    review_dir / "normalized" / "invoice"
                )
                if normalized["invoice"]
                else [],
            }
            linearized = build_linearized_document(ocr_payload)
            output_paths = write_linearized_outputs(
                linearized,
                review_dir / "ocr",
            )
            ocr_path = self.store.write_result(
                manifest.review_id,
                "ocr/document.json",
                ocr_payload,
            )
            manifest.normalized_pages = {
                role: [str(path) for path in paths]
                for role, paths in normalized.items()
            }
            manifest.artifacts.update(
                {
                    "ocr_payload": str(ocr_path),
                    "contract_text": output_paths["contract"],
                    "attachments_text": output_paths["attachments"],
                    "invoice_text": output_paths["invoice"],
                }
            )
            manifest.steps["prepare_contract"] = ReviewStepRecord(
                status="completed",
                result_path="ocr/document.json",
                versions=versions,
            )
            self.store.save(manifest)
        except Exception as exc:
            manifest.steps["prepare_contract"] = ReviewStepRecord(
                status="failed",
                versions=versions,
                error=str(exc),
            )
            self.store.save(manifest)
            raise

        return {
            "review_id": manifest.review_id,
            "cached": False,
            "artifacts": manifest.artifacts,
        }

    def run_step(
        self,
        review_id: str,
        step_name: str,
        operation: ReviewOperation,
        required_versions: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self._check_cancelled()
        manifest = self.store.load(review_id)
        versions = (
            required_versions
            if required_versions is not None
            else self._required_versions(step_name, manifest)
        )
        record = manifest.steps.get(step_name)
        if is_step_current(record, versions) and record and record.result_path:
            result = self.store.read_result(review_id, record.result_path)
            return {**result, "cached": True}

        result_path = f"results/{step_name}.json"
        manifest.steps[step_name] = ReviewStepRecord(
            status="running",
            result_path=result_path,
            versions=versions,
        )
        self.store.save(manifest)
        try:
            result = operation()
            self.store.write_result(review_id, result_path, result)
            manifest = self.store.load(review_id)
            manifest.steps[step_name] = ReviewStepRecord(
                status="completed",
                result_path=result_path,
                versions=versions,
            )
            self.store.save(manifest)
        except Exception as exc:
            manifest = self.store.load(review_id)
            manifest.steps[step_name] = ReviewStepRecord(
                status="failed",
                result_path=result_path,
                versions=versions,
                error=str(exc),
            )
            self.store.save(manifest)
            return {
                "review_status": "execution_failed",
                "error": str(exc),
                "cached": False,
            }
        return {**result, "cached": False}

    def check_basic_info(self, review_id: str) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            manifest = self.store.load(review_id)
            contract_text = Path(manifest.artifacts["contract_text"]).read_text(
                encoding="utf-8"
            )
            extracted = self.extract_basic_info(contract_text)
            platform_data = manifest.inputs.get("platform_basic_info")
            if not platform_data:
                return {
                    "review_status": "not_executed",
                    "reason": "未提供平台基础信息。",
                    "contract_basic_info": extracted.model_dump(),
                    "compare_result": None,
                    "summary": None,
                }
            platform = ContractBasicInfo.model_validate(platform_data)
            compare_result, flat_result = compare_basic_info(extracted, platform)
            return {
                "review_status": "completed",
                "reason": "",
                "contract_basic_info": extracted.model_dump(),
                "compare_result": compare_result.model_dump(),
                "summary": build_summary(flat_result).model_dump(),
            }

        return self.run_step(review_id, "check_basic_info", operation)

    def _contract_ocr_pages(self, review_id: str) -> list[dict[str, Any]]:
        manifest = self.store.load(review_id)
        return json.loads(
            Path(manifest.artifacts["ocr_payload"]).read_text(encoding="utf-8")
        )["contract"]

    def _contract_page_texts(self, review_id: str) -> list[ContractPageText]:
        return [
            ContractPageText(
                page_index=index,
                page_text=linearize_ocr_page(page),
            )
            for index, page in enumerate(
                self._contract_ocr_pages(review_id),
                start=1,
            )
        ]

    def check_text_integrity(self, review_id: str) -> dict[str, Any]:
        return self.run_step(
            review_id,
            "check_text_integrity",
            lambda: asdict(
                self.review_text_integrity(
                    self._contract_page_texts(review_id)
                )
            ),
        )

    def check_contract_seals(self, review_id: str) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            manifest = self.store.load(review_id)
            candidates = [
                candidate
                for page_index, image_path in enumerate(
                    manifest.normalized_pages.get("contract", []),
                    start=1,
                )
                for candidate in self.detect_seals(image_path, page_index)
            ]
            return asdict(
                self.review_seals(
                    self._contract_page_texts(review_id),
                    candidates,
                )
            )

        return self.run_step(review_id, "check_contract_seals", operation)

    def check_cross_page_seal(self, review_id: str) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            manifest = self.store.load(review_id)
            image_paths = [
                Path(path)
                for path in manifest.normalized_pages.get("contract", [])
            ]
            return asdict(self.review_cross_page_seal(image_paths))

        return self.run_step(review_id, "check_cross_page_seal", operation)

    def check_contract_authenticity(
        self,
        review_id: str,
        *,
        search_enabled: bool = True,
    ) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            manifest = self.store.load(review_id)
            basic_info_result = self.check_basic_info(review_id)
            basic_info = basic_info_result.get("contract_basic_info")
            if not basic_info:
                error = basic_info_result.get("error") or "基础信息结果不可用"
                raise RuntimeError(
                    f"basic info dependency failed: {error}"
                )
            contract_text = Path(manifest.artifacts["contract_text"]).read_text(
                encoding="utf-8"
            )
            return self.review_authenticity(
                contract_text=contract_text,
                basic_info=basic_info,
                search_enabled=search_enabled,
            )

        return self.run_step(
            review_id,
            "check_contract_authenticity",
            operation,
        )

    def write_review_report(self, review_id: str) -> dict[str, Any]:
        manifest = self.store.load(review_id)
        missing_steps = [
            name
            for name in REQUIRED_REVIEW_STEPS
            if name not in manifest.steps
        ]
        stale_steps = [
            name
            for name in REQUIRED_REVIEW_STEPS
            if (
                (record := manifest.steps.get(name))
                and record.status == "completed"
                and not is_step_current(
                    record,
                    self._required_versions(name, manifest),
                )
            )
        ]
        if missing_steps or stale_steps:
            return {
                "review_status": "blocked",
                "missing_steps": missing_steps,
                "stale_steps": stale_steps,
                "cached": False,
            }
        report_versions = self._required_versions(
            "write_review_report",
            manifest,
        )

        def operation() -> dict[str, Any]:
            current = self.store.load(review_id)
            sections: dict[str, Any] = {}
            for name, record in current.steps.items():
                if name in {"prepare_contract", "write_review_report"}:
                    continue
                if record.status == "completed" and record.result_path:
                    result = self.store.read_result(review_id, record.result_path)
                    status = _classify_result(name, result)
                elif record.status == "failed":
                    result = {"error": record.error}
                    status = "execution_failed"
                else:
                    result = None
                    status = "not_executed"
                sections[name] = {"status": status, "result": result}

            section_statuses = {
                section["status"] for section in sections.values()
            }
            if "risk" in section_statuses:
                overall_status = "risk"
            elif section_statuses & {
                "unknown",
                "not_executed",
                "execution_failed",
            }:
                overall_status = "unknown"
            else:
                overall_status = "passed"

            report = {
                "review_id": review_id,
                "overall_status": overall_status,
                "sections": sections,
                "json_path": "reports/contract_review.json",
                "markdown_path": "reports/contract_review.md",
            }
            self.store.write_result(
                review_id,
                report["json_path"],
                report,
            )
            markdown_path = self.store.review_dir(review_id) / report["markdown_path"]
            markdown_path.write_text(
                _render_report_markdown(report),
                encoding="utf-8",
            )
            return report

        return self.run_step(
            review_id,
            "write_review_report",
            operation,
            required_versions=report_versions,
        )

    def get_review_status(self, review_id: str) -> dict[str, Any]:
        try:
            manifest = self.store.load(review_id)
        except FileNotFoundError:
            return {
                "review_id": review_id,
                "error": True,
                "error_type": "NotFoundError",
                "message": f"审核任务不存在: {review_id}",
            }
        except Exception as exc:
            return {
                "review_id": review_id,
                "error": True,
                "error_type": type(exc).__name__,
                "message": f"加载审核任务失败: {exc}",
            }
        steps = {}
        for name, record in manifest.steps.items():
            current = is_step_current(
                record,
                self._required_versions(name, manifest),
            )
            status = record.status if current or record.status != "completed" else "stale"
            steps[name] = {**record.model_dump(), "status": status}
        missing_steps = [
            name
            for name in REQUIRED_REVIEW_STEPS
            if name not in manifest.steps
        ]
        stale_steps = [
            name
            for name in REQUIRED_REVIEW_STEPS
            if (steps.get(name) or {}).get("status") == "stale"
        ]
        return {
            "review_id": review_id,
            "contract_fingerprint": manifest.contract_fingerprint,
            "material_fingerprint": manifest.material_fingerprint,
            "steps": steps,
            "missing_steps": missing_steps,
            "stale_steps": stale_steps,
            "ready_for_report": not missing_steps and not stale_steps,
            "artifacts": manifest.artifacts,
        }

    def get_review_result(
        self,
        review_id: str,
        step_name: str = "",
    ) -> dict[str, Any]:
        try:
            manifest = self.store.load(review_id)
        except FileNotFoundError:
            return {
                "review_id": review_id,
                "error": True,
                "error_type": "NotFoundError",
                "message": f"审核任务不存在: {review_id}",
            }
        except Exception as exc:
            return {
                "review_id": review_id,
                "error": True,
                "error_type": type(exc).__name__,
                "message": f"加载审核任务失败: {exc}",
            }
        if step_name:
            record = manifest.steps.get(step_name)
            if not record or not record.result_path:
                return {
                    "review_id": review_id,
                    "error": True,
                    "error_type": "KeyError",
                    "message": f"审核步骤无结果: {step_name}",
                }
            try:
                return self.store.read_result(review_id, record.result_path)
            except Exception as exc:
                return {
                    "review_id": review_id,
                    "error": True,
                    "error_type": type(exc).__name__,
                    "message": f"读取审核结果失败 ({step_name}): {exc}",
                }
        try:
            return {
                name: self.store.read_result(review_id, record.result_path)
                for name, record in manifest.steps.items()
                if record.status == "completed" and record.result_path
            }
        except Exception as exc:
            return {
                "review_id": review_id,
                "error": True,
                "error_type": type(exc).__name__,
                "message": f"读取审核结果失败: {exc}",
            }


_current_service: contextvars.ContextVar[ContractReviewService | None] = (
    contextvars.ContextVar("contract_review_service", default=None)
)


def set_contract_review_service(service: ContractReviewService) -> None:
    """为当前请求上下文设置服务实例（API 层调用）。"""
    _current_service.set(service)


def get_contract_review_service() -> ContractReviewService:
    """获取当前上下文的审核服务实例。

    API 请求中返回请求级实例（支持取消隔离）；
    CLI 等非 Web 场景回退到默认实例。
    """
    svc = _current_service.get()
    if svc is not None:
        return svc
    from .versions import build_default_capability_versions

    return ContractReviewService(versions=build_default_capability_versions())
