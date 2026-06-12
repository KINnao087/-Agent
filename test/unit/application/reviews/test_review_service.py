from __future__ import annotations

from pathlib import Path
from dataclasses import asdict
from unittest.mock import Mock

import pytest

from core.application.reviews import ContractReviewService
from core.domain.contracts import CPSealResult
from core.domain.contracts.integrity_models import (
    ContractContinuityResult,
    ContractSealIntegrityResult,
    TextIntegrityReviewResult,
)
from core.domain.contracts.models import ContractBasicInfo
from core.domain.reviews import ReviewStepRecord
from core.infrastructure.reviews import FileReviewStore
from core.infrastructure.vision.seal.models import SealCandidate


def _write_page(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_prepare_contract_reuses_completed_ocr(tmp_path) -> None:
    source_page = _write_page(tmp_path / "source.png", b"contract-page")
    normalized_page = _write_page(tmp_path / "normalized.png", b"contract-page")
    normalizer = Mock(return_value=[normalized_page])
    ocr_loader = Mock(
        return_value=[
            {
                "input_path": str(normalized_page),
                "rec_texts": ["合同编号 HT-1"],
                "rec_scores": [0.99],
            }
        ]
    )
    service = ContractReviewService(
        store=FileReviewStore(tmp_path / "reviews"),
        normalize_images=normalizer,
        load_ocr_pages=ocr_loader,
        versions={"prepare_contract": {"ocr": "ocr-v1"}},
    )

    first = service.prepare_contract(str(source_page))
    second = service.prepare_contract(str(source_page))

    assert second["review_id"] == first["review_id"]
    assert second["cached"] is True
    assert ocr_loader.call_count == 1
    manifest = service.store.load(first["review_id"])
    assert manifest.steps["prepare_contract"].status == "completed"
    assert Path(manifest.artifacts["contract_text"]).read_text(encoding="utf-8")


def test_prepare_contract_rebuilds_missing_cached_artifact(tmp_path) -> None:
    source_page = _write_page(tmp_path / "source.png", b"contract-page")
    normalized_page = _write_page(tmp_path / "normalized.png", b"contract-page")
    ocr_loader = Mock(
        return_value=[
            {
                "input_path": str(normalized_page),
                "rec_texts": ["合同"],
                "rec_scores": [0.99],
            }
        ]
    )
    service = ContractReviewService(
        store=FileReviewStore(tmp_path / "reviews"),
        normalize_images=Mock(return_value=[normalized_page]),
        load_ocr_pages=ocr_loader,
        versions={"prepare_contract": {"ocr": "ocr-v1"}},
    )
    first = service.prepare_contract(str(source_page))
    manifest = service.store.load(first["review_id"])
    Path(manifest.artifacts["contract_text"]).unlink()

    second = service.prepare_contract(str(source_page))

    assert second["cached"] is False
    assert ocr_loader.call_count == 2


def test_prepare_contract_rejects_input_without_contract_pages(tmp_path) -> None:
    service = ContractReviewService(
        store=FileReviewStore(tmp_path / "reviews"),
        normalize_images=Mock(return_value=[]),
    )

    with pytest.raises(ValueError, match="no contract pages"):
        service.prepare_contract(str(tmp_path / "empty"))


def test_basic_info_without_platform_data_is_recorded_as_not_reviewed(tmp_path) -> None:
    store = FileReviewStore(tmp_path / "reviews")
    manifest = store.create_or_load(
        contract_fingerprint="contract",
        material_fingerprint="material",
        inputs={"platform_basic_info": None},
    )
    text_path = store.review_dir(manifest.review_id) / "ocr" / "contract.txt"
    text_path.write_text("合同编号 HT-1", encoding="utf-8")
    manifest.artifacts["contract_text"] = str(text_path)
    store.save(manifest)
    extractor = Mock(return_value=ContractBasicInfo(contract_no="HT-1"))
    service = ContractReviewService(
        store=store,
        extract_basic_info=extractor,
        versions={"check_basic_info": {"model": "m1", "prompt": "p1"}},
    )

    result = service.check_basic_info(manifest.review_id)

    assert result["review_status"] == "not_executed"
    assert result["reason"] == "未提供平台基础信息。"
    assert result["contract_basic_info"]["contract_no"] == "HT-1"
    assert extractor.call_count == 1


def test_completed_business_step_is_loaded_without_reexecuting_operation(tmp_path) -> None:
    store = FileReviewStore(tmp_path / "reviews")
    manifest = store.create_or_load(
        contract_fingerprint="contract",
        material_fingerprint="material",
        inputs={},
    )
    operation = Mock(return_value={"status": "complete"})
    service = ContractReviewService(
        store=store,
        versions={"check_text_integrity": {"model": "m1", "prompt": "p1"}},
    )

    first = service.run_step(
        manifest.review_id,
        "check_text_integrity",
        operation,
    )
    second = service.run_step(
        manifest.review_id,
        "check_text_integrity",
        operation,
    )

    assert first["cached"] is False
    assert second == {"status": "complete", "cached": True}
    assert operation.call_count == 1


def test_failed_business_step_is_persisted_and_does_not_abort_other_steps(tmp_path) -> None:
    store = FileReviewStore(tmp_path / "reviews")
    manifest = store.create_or_load(
        contract_fingerprint="contract",
        material_fingerprint="material",
        inputs={},
    )
    service = ContractReviewService(store=store)

    result = service.run_step(
        manifest.review_id,
        "check_contract_authenticity",
        Mock(side_effect=RuntimeError("search unavailable")),
    )

    assert result == {
        "review_status": "execution_failed",
        "error": "search unavailable",
        "cached": False,
    }
    record = store.load(manifest.review_id).steps["check_contract_authenticity"]
    assert record.status == "failed"
    assert record.error == "search unavailable"


def _prepared_review(tmp_path):
    store = FileReviewStore(tmp_path / "reviews")
    manifest = store.create_or_load(
        contract_fingerprint="contract",
        material_fingerprint="material",
        inputs={},
    )
    page_path = _write_page(
        store.review_dir(manifest.review_id) / "normalized" / "contract" / "page-0001.png",
        b"page",
    )
    ocr_payload = {
        "contract": [
            {
                "input_path": str(page_path),
                "rec_texts": ["合同正文"],
                "rec_scores": [0.99],
            }
        ],
        "attachments": [],
        "invoice": [],
    }
    ocr_path = store.write_result(manifest.review_id, "ocr/document.json", ocr_payload)
    text_path = store.review_dir(manifest.review_id) / "ocr" / "contract.txt"
    text_path.write_text("合同正文", encoding="utf-8")
    manifest.normalized_pages["contract"] = [str(page_path)]
    manifest.artifacts.update(
        {"ocr_payload": str(ocr_path), "contract_text": str(text_path)}
    )
    store.save(manifest)
    return store, manifest


def test_text_integrity_and_normal_seals_are_independent_steps(tmp_path) -> None:
    store, manifest = _prepared_review(tmp_path)
    text_result = TextIntegrityReviewResult(
        contract_continuity=ContractContinuityResult(status="continuous")
    )
    integrity_reviewer = Mock(return_value=text_result)
    candidate = SealCandidate(
        page_index=1,
        image_path=manifest.normalized_pages["contract"][0],
        bbox=[0, 0, 10, 10],
    )
    detector = Mock(return_value=[candidate])
    seal_result = ContractSealIntegrityResult()
    seal_reviewer = Mock(return_value=seal_result)
    service = ContractReviewService(
        store=store,
        review_text_integrity=integrity_reviewer,
        detect_seals=detector,
        review_seals=seal_reviewer,
        versions={
            "check_text_integrity": {"prompt": "integrity-v1"},
            "check_contract_seals": {"prompt": "seal-v1"},
        },
    )

    integrity = service.check_text_integrity(manifest.review_id)
    seals = service.check_contract_seals(manifest.review_id)

    assert integrity["contract_continuity"]["status"] == "continuous"
    assert "contract_seal_integrity" not in integrity
    assert seals == {**asdict(seal_result), "cached": False}
    integrity_reviewer.assert_called_once()
    detector.assert_called_once()
    seal_reviewer.assert_called_once()


def test_cross_page_and_authenticity_steps_use_prepared_context(tmp_path) -> None:
    store, manifest = _prepared_review(tmp_path)
    basic_info_path = store.write_result(
        manifest.review_id,
        "results/check_basic_info.json",
        {
            "review_status": "not_executed",
            "contract_basic_info": ContractBasicInfo(
                seller={"name": "乙方"},
                buyer={"name": "甲方"},
            ).model_dump(),
        },
    )
    loaded = store.load(manifest.review_id)
    loaded.steps["check_basic_info"] = ReviewStepRecord(
        status="completed",
        result_path=str(
            basic_info_path.relative_to(store.review_dir(manifest.review_id))
        ),
        versions={},
    )
    store.save(loaded)
    cross_page_reviewer = Mock(
        return_value=CPSealResult(status="present", page_count=1)
    )
    authenticity_reviewer = Mock(
        return_value={"conclusion": "likely_valid", "risk_points": []}
    )
    service = ContractReviewService(
        store=store,
        review_cross_page_seal=cross_page_reviewer,
        review_authenticity=authenticity_reviewer,
    )

    cross_page = service.check_cross_page_seal(manifest.review_id)
    authenticity = service.check_contract_authenticity(manifest.review_id)

    assert cross_page["status"] == "present"
    assert authenticity["conclusion"] == "likely_valid"
    cross_page_reviewer.assert_called_once_with(
        [Path(manifest.normalized_pages["contract"][0])]
    )
    authenticity_reviewer.assert_called_once()
