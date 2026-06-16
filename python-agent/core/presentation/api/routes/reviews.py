from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse

from core.application.agent.chat_service import CliChatService, TraceEvent
from core.application.reviews import (
    ContractReviewService,
    set_contract_review_service,
)
from core.application.workflows.chat import build_chat_graph
from core.shared.logging import get_logger

_logger = get_logger("api.reviews")
router = APIRouter(prefix="/api/reviews", tags=["reviews"])

# 全局取消信号注册表: review_id → threading.Event
_cancel_registry: dict[str, threading.Event] = {}
_registry_lock = threading.Lock()


def _get_or_create_cancel_event(review_id: str) -> threading.Event:
    with _registry_lock:
        if review_id not in _cancel_registry:
            _cancel_registry[review_id] = threading.Event()
        return _cancel_registry[review_id]


def _remove_cancel_event(review_id: str) -> None:
    with _registry_lock:
        _cancel_registry.pop(review_id, None)


def _build_review_prompt(
    contract_path: str,
    attachments_path: str = "",
    invoice_path: str = "",
    platform_basic_info: dict[str, Any] | None = None,
) -> str:
    """构建发送给 AI Agent 的审核指令。"""
    parts = [
        "请对以下合同执行完整的8步审核流程：",
        f"1. find_contract_review: contract_path='{contract_path}'"
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


def _make_service(cancel_event: threading.Event | None = None) -> ContractReviewService:
    """创建请求级审核服务实例。"""
    from core.application.reviews.versions import build_default_capability_versions

    return ContractReviewService(
        versions=build_default_capability_versions(),
        cancel_event=cancel_event,
    )


@router.post("")
async def create_review(payload: dict[str, Any]) -> dict[str, Any]:
    """创建审核任务 — 执行 prepare_contract 并返回 review_id。"""
    contract_path = str(payload.get("contract_path", ""))
    if not contract_path:
        raise HTTPException(status_code=400, detail="缺少 contract_path")

    platform_info = payload.get("platform_basic_info")
    if not platform_info or not isinstance(platform_info, dict):
        platform_info = None

    _logger.info("收到审核请求: contract_path={}", contract_path)

    service = _make_service()
    set_contract_review_service(service)
    try:
        result = service.prepare_contract(
            contract_path=contract_path,
            attachments_path=str(payload.get("attachments_path", "")),
            invoice_path=str(payload.get("invoice_path", "")),
            platform_basic_info=platform_info,
        )
        _logger.info("审核任务创建成功: {}", result["review_id"])
        return {"review_id": result["review_id"], "cached": result.get("cached", False)}
    except Exception as exc:
        _logger.error("创建审核任务失败: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        set_contract_review_service(None)  # type: ignore[arg-type]


@router.get("/{review_id}/stream")
async def stream_review(review_id: str, request: Request) -> StreamingResponse:
    """SSE 流式推送 AI 审核工具调用链。

    前端用 EventSource 连接此端点，实时接收 TraceEvent。
    """
    cancel_event = _get_or_create_cancel_event(review_id)
    cancel_event.clear()

    # 创建请求级服务实例并注入上下文
    service = _make_service(cancel_event=cancel_event)
    set_contract_review_service(service)

    # 获取审核任务输入参数
    try:
        manifest = service.store.load(review_id)
        inputs = manifest.inputs
    except FileNotFoundError:
        _remove_cancel_event(review_id)
        raise HTTPException(status_code=404, detail=f"审核任务不存在: {review_id}")

    prompt = _build_review_prompt(
        contract_path=inputs.get("contract_path", ""),
        attachments_path=inputs.get("attachments_path", ""),
        invoice_path=inputs.get("invoice_path", ""),
        platform_basic_info=inputs.get("platform_basic_info"),
    )

    chat_service = CliChatService(
        graph=build_chat_graph(),
        thread_id=f"api-{review_id}",
        cancel_event=cancel_event,
    )

    async def event_generator():
        try:
            # 在线程池中运行同步 LangGraph 流，避免阻塞事件循环
            loop = asyncio.get_running_loop()
            stream = chat_service.stream(prompt)
            while True:
                # 检查客户端是否断开
                if await request.is_disconnected():
                    cancel_event.set()
                    _logger.info("客户端断开连接，取消审核: {}", review_id)
                    break
                try:
                    event: TraceEvent = await loop.run_in_executor(
                        None, next, stream
                    )
                    data = json.dumps(
                        {
                            "kind": event.kind,
                            "summary": event.summary,
                            "detail": event.detail,
                            "node": event.node,
                            "tool_call_id": event.tool_call_id,
                            "tool_name": event.tool_name,
                            "elapsed_ms": event.elapsed_ms,
                            "is_error": event.is_error,
                        },
                        ensure_ascii=False,
                    )
                    yield f"data: {data}\n\n"
                    if event.kind in ("final", "error"):
                        break
                except StopIteration:
                    break
        except Exception as exc:
            _logger.error("SSE 流式推送失败: {}", exc)
            error_data = json.dumps(
                {
                    "kind": "error",
                    "summary": f"服务异常: {exc}",
                    "detail": str(exc),
                    "is_error": True,
                },
                ensure_ascii=False,
            )
            yield f"data: {error_data}\n\n"
        finally:
            _remove_cancel_event(review_id)
            # 清理上下文
            set_contract_review_service(None)  # type: ignore[arg-type]

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
    """查询审核任务进度。"""
    service = _make_service()
    set_contract_review_service(service)
    try:
        return service.get_review_status(review_id)
    finally:
        set_contract_review_service(None)  # type: ignore[arg-type]


@router.get("/{review_id}/report")
async def get_review_report(review_id: str) -> dict[str, Any]:
    """获取审核报告 JSON。"""
    service = _make_service()
    set_contract_review_service(service)
    try:
        return service.get_review_result(review_id)
    finally:
        set_contract_review_service(None)  # type: ignore[arg-type]


@router.get("/{review_id}/report/markdown")
async def get_review_report_markdown(review_id: str) -> PlainTextResponse:
    """获取审核报告 Markdown 原文。"""
    service = _make_service()
    md_path = service.store.review_dir(review_id) / "reports" / "contract_review.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="Markdown 报告尚未生成")
    return PlainTextResponse(
        md_path.read_text(encoding="utf-8"),
        media_type="text/markdown",
    )


@router.delete("/{review_id}")
async def cancel_review(review_id: str) -> dict[str, Any]:
    """取消正在执行的审核任务。"""
    cancel_event = _get_or_create_cancel_event(review_id)
    cancel_event.set()
    return {"review_id": review_id, "cancelled": True}
