from __future__ import annotations

import json
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Iterator
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph.state import CompiledStateGraph

from core.application.workflows.chat import build_chat_graph


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """A safe, structured description of one agent execution event."""

    kind: str
    summary: str
    detail: str = ""
    node: str = ""
    tool_call_id: str = ""
    tool_name: str = ""
    elapsed_ms: float | None = None
    is_error: bool = False


def _json_detail(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except (TypeError, ValueError):
        return str(value)


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        if parts:
            return "\n".join(part for part in parts if part)
    return str(content)


def _truncate(text: str, max_chars: int = 240) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return f"{compact[:max_chars - 3]}..."


def _tool_result(content: Any) -> tuple[str, str, bool]:
    text = _message_text(content)
    try:
        value = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return _truncate(text), text, False

    detail = _json_detail(value)
    if not isinstance(value, dict):
        return _truncate(detail), detail, False

    is_error = bool(value.get("error"))
    if is_error:
        summary = str(value.get("message") or value.get("error_type") or "工具执行失败")
        return _truncate(summary), detail, True

    summary_fields = (
        "review_status",
        "overall_status",
        "status",
        "found",
        "review_id",
        "cached",
        "ready_for_report",
    )
    selected = {
        key: value[key]
        for key in summary_fields
        if key in value
    }
    summary = _json_detail(selected or value)
    return _truncate(summary), detail, False


@dataclass(slots=True)
class CliChatService:
    graph: CompiledStateGraph
    thread_id: str

    def stream(self, message: str) -> Iterator[TraceEvent]:
        """Stream an auditable execution trace and the final answer."""
        pending_tools: dict[str, tuple[str, float]] = {}
        yield TraceEvent(
            kind="turn_start",
            summary="开始处理用户请求",
            detail=message,
        )
        try:
            updates = self.graph.stream(
                {"messages": [HumanMessage(content=message)]},
                config={"configurable": {"thread_id": self.thread_id}},
                stream_mode="updates",
            )
            for update in updates:
                if not isinstance(update, dict):
                    continue
                for node, payload in update.items():
                    if not isinstance(payload, dict):
                        continue
                    messages = payload.get("messages", [])
                    if not isinstance(messages, list):
                        messages = [messages]
                    for current in messages:
                        if isinstance(current, AIMessage):
                            if current.tool_calls:
                                yield TraceEvent(
                                    kind="decision",
                                    node=node,
                                    summary=f"模型决定调用 {len(current.tool_calls)} 个工具",
                                    detail=_json_detail(current.tool_calls),
                                )
                                for call in current.tool_calls:
                                    call_id = str(call.get("id", ""))
                                    tool_name = str(call.get("name", "未知工具"))
                                    args = call.get("args", {})
                                    pending_tools[call_id] = (tool_name, perf_counter())
                                    yield TraceEvent(
                                        kind="tool_start",
                                        node=node,
                                        summary=f"调用 {tool_name}",
                                        detail=_json_detail(args),
                                        tool_call_id=call_id,
                                        tool_name=tool_name,
                                    )
                            else:
                                answer = _message_text(current.content)
                                if answer:
                                    yield TraceEvent(
                                        kind="final",
                                        node=node,
                                        summary=_truncate(answer),
                                        detail=answer,
                                    )
                        elif isinstance(current, ToolMessage):
                            call_id = current.tool_call_id
                            tool_name, started_at = pending_tools.pop(
                                call_id,
                                (current.name or "未知工具", perf_counter()),
                            )
                            summary, detail, content_error = _tool_result(
                                current.content
                            )
                            is_error = (
                                current.status == "error" or content_error
                            )
                            yield TraceEvent(
                                kind="tool_result",
                                node=node,
                                summary=summary,
                                detail=detail,
                                tool_call_id=call_id,
                                tool_name=tool_name,
                                elapsed_ms=(perf_counter() - started_at) * 1000,
                                is_error=is_error,
                            )
        except Exception as exc:
            yield TraceEvent(
                kind="error",
                summary=f"Agent 执行失败: {exc}",
                detail=f"{type(exc).__name__}: {exc}",
                is_error=True,
            )

    def ask(self, message: str) -> str:
        answer = ""
        error = ""
        for event in self.stream(message):
            if event.kind == "final":
                answer = event.detail
            elif event.kind == "error":
                error = event.detail or event.summary
        if answer:
            return answer
        if error:
            raise RuntimeError(error)
        raise RuntimeError("Agent 未返回最终回答")


def create_cli_chat_service() -> CliChatService:
    return CliChatService(
        graph=build_chat_graph(),
        thread_id=str(uuid4()),
    )
