from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse

from core.application.reviews import (
    ContractReviewService,
    set_contract_review_service,
)
from core.presentation.api.review_runtime import (
    TERMINAL_EVENT_KINDS,
    ReviewEventStore,
    ReviewRuntimeManager,
)
from core.shared.logging import get_logger

_logger = get_logger("api.reviews")
router = APIRouter(prefix="/api/reviews", tags=["reviews"])


def _build_review_prompt(
    contract_path: str,
    attachments_path: str = "",
    invoice_path: str = "",
    platform_basic_info: dict[str, Any] | None = None,
) -> str:
    parts = [
        "请对以下合同执行完整的 AI 审核流程：",
        f"1. find_contract_review: contract_path={contract_path!r}"
        f"{', attachments_path=' + repr(attachments_path) if attachments_path else ''}"
        f"{', invoice_path=' + repr(invoice_path) if invoice_path else ''}"
        f"{', platform_basic_info=' + json.dumps(platform_basic_info, ensure_ascii=False) if platform_basic_info else ''}",
        "",
        "2. prepare_contract（使用上一步返回的 material_fingerprint 和路径信息）",
        "3. check_basic_info",
        "4. check_text_integrity",
        "5. check_contract_seals",
        "6. check_cross_page_seal",
        "7. check_contract_authenticity",
        "8. write_review_report",
        "",
        f"合同路径: {contract_path}",
    ]
    if attachments_path:
        parts.append(f"附件路径: {attachments_path}")
    if invoice_path:
        parts.append(f"发票路径: {invoice_path}")
    if platform_basic_info:
        parts.append(
            f"平台基础信息: {json.dumps(platform_basic_info, ensure_ascii=False)}"
        )
    return "\n".join(parts)


def _make_service(cancel_event=None) -> ContractReviewService:
    from core.application.reviews.versions import build_default_capability_versions

    return ContractReviewService(
        versions=build_default_capability_versions(),
        cancel_event=cancel_event,
    )


_event_store = ReviewEventStore()
_runtime = ReviewRuntimeManager(
    event_store=_event_store,
    make_service=_make_service,
    build_prompt=_build_review_prompt,
)


def _with_service(fn):
    service = _make_service()
    set_contract_review_service(service)
    try:
        return fn(service)
    finally:
        set_contract_review_service(None)  # type: ignore[arg-type]


def _load_review(review_id: str) -> None:
    def _load(service: ContractReviewService) -> None:
        service.store.load(review_id)

    _with_service(_load)


def _ensure_terminal_event(review_id: str, *, cancelled: bool = False) -> None:
    last_seq = _event_store.last_seq(review_id)
    if last_seq > 0:
        recent = _event_store.read_after(review_id, after_seq=max(0, last_seq - 1))
        if recent and recent[-1]["kind"] in TERMINAL_EVENT_KINDS:
            return

    status = _with_service(lambda service: service.get_review_status(review_id))
    _runtime.append_terminal_event(
        review_id=review_id,
        status=status,
        cancelled=cancelled,
    )


@router.post("")
async def create_review(payload: dict[str, Any]) -> dict[str, Any]:
    contract_path = str(payload.get("contract_path", ""))
    if not contract_path:
        raise HTTPException(status_code=400, detail="缺少 contract_path")

    attachments_path = str(payload.get("attachments_path", ""))
    invoice_path = str(payload.get("invoice_path", ""))
    platform_info = payload.get("platform_basic_info")
    if not platform_info or not isinstance(platform_info, dict):
        platform_info = None

    _logger.info("Received review request: contract_path={}", contract_path)

    def _prepare(service: ContractReviewService) -> dict[str, Any]:
        result = service.prepare_contract(
            contract_path=contract_path,
            attachments_path=attachments_path,
            invoice_path=invoice_path,
            platform_basic_info=platform_info,
        )
        status = service.get_review_status(result["review_id"])
        return {"result": result, "status": status}

    try:
        prepared = _with_service(_prepare)
        review_id = prepared["result"]["review_id"]
        status = prepared["status"]
        started = False
        if status.get("ready_for_report"):
            _ensure_terminal_event(review_id)
        else:
            started = _runtime.start(
                review_id=review_id,
                contract_path=contract_path,
                attachments_path=attachments_path,
                invoice_path=invoice_path,
                platform_basic_info=platform_info,
            )
        status["execution_state"] = _runtime.state(review_id)
        status["last_event_seq"] = _event_store.last_seq(review_id)
        return {
            "review_id": review_id,
            "cached": prepared["result"].get("cached", False),
            "started": started,
            "status": status,
        }
    except Exception as exc:
        _logger.error("Failed to create review: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{review_id}/stream")
async def stream_review(
    review_id: str,
    request: Request,
    after_seq: int = 0,
) -> StreamingResponse:
    try:
        _load_review(review_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"审核任务不存在: {review_id}")

    async def event_generator():
        last_seq = after_seq
        try:
            while True:
                if await request.is_disconnected():
                    _logger.info("Client disconnected from review stream: {}", review_id)
                    return

                events = _event_store.read_after(review_id, after_seq=last_seq)
                if events:
                    for event in events:
                        last_seq = int(event["seq"])
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                        if event["kind"] in TERMINAL_EVENT_KINDS:
                            return
                else:
                    execution_state = _runtime.state(review_id)
                    if execution_state in {"completed", "failed", "cancelled"}:
                        _ensure_terminal_event(
                            review_id,
                            cancelled=execution_state == "cancelled",
                        )
                        continue
                    if execution_state == "idle" and last_seq == 0:
                        _ensure_terminal_event(review_id)
                        continue

                await asyncio.sleep(0.5)
        except Exception as exc:
            _logger.error("Failed to stream review events: review_id={}", review_id)
            payload = {
                "seq": last_seq + 1,
                "timestamp": "",
                "review_id": review_id,
                "kind": "error",
                "summary": f"服务异常: {exc}",
                "detail": str(exc),
                "node": "",
                "tool_call_id": "",
                "tool_name": "",
                "elapsed_ms": None,
                "is_error": True,
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/{review_id}/status")
async def get_review_status(review_id: str) -> dict[str, Any]:
    status = _with_service(lambda service: service.get_review_status(review_id))
    status["execution_state"] = _runtime.state(review_id)
    status["last_event_seq"] = _event_store.last_seq(review_id)
    return status


@router.get("/{review_id}/report")
async def get_review_report(review_id: str) -> dict[str, Any]:
    return _with_service(lambda service: service.get_review_result(review_id))


@router.get("/{review_id}/report/markdown")
async def get_review_report_markdown(review_id: str) -> PlainTextResponse:
    def _read(service: ContractReviewService) -> str:
        md_path = service.store.review_dir(review_id) / "reports" / "contract_review.md"
        if not md_path.exists():
            raise HTTPException(status_code=404, detail="Markdown 报告尚未生成")
        return md_path.read_text(encoding="utf-8")

    return PlainTextResponse(
        _with_service(_read),
        media_type="text/markdown",
    )


@router.delete("/{review_id}")
async def cancel_review(review_id: str) -> dict[str, Any]:
    _runtime.cancel(review_id)
    return {"review_id": review_id, "cancelled": True}
