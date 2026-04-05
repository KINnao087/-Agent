from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

AssistantResponseKind = Literal["to_user", "ask_user", "tool_call"]


@dataclass(slots=True)
class AssistantResponse:
    """控制层 assistant 的结构化响应。"""

    kind: AssistantResponseKind
    message: str = ""
    name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)


def _strict_json_object(content: str) -> dict[str, Any]:
    """严格解析 assistant 响应，要求内容本体就是单个 JSON 对象。"""
    text = (content or "").strip()
    if not text:
        raise ValueError("assistant response is empty")
    if not (text.startswith("{") and text.endswith("}")):
        raise ValueError("assistant response must be exactly one JSON object")

    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("assistant response JSON must be an object")
    return data


def parse_assistant_response(content: str) -> AssistantResponse:
    """把控制层 assistant 文本解析成结构化响应对象。"""
    data = _strict_json_object(content)

    raw_type = str(data.get("type") or data.get("kind") or "").strip().lower()
    kind_aliases = {
        "to_user": "to_user",
        "touser": "to_user",
        "ask_user": "ask_user",
        "askuser": "ask_user",
        "tool_call": "tool_call",
        "toolcall": "tool_call",
    }
    kind = kind_aliases.get(raw_type)
    if kind is None:
        raise ValueError("assistant response JSON must contain a valid type")

    if kind in {"to_user", "ask_user"}:
        message = data.get("message")
        if not isinstance(message, str) or not message.strip():
            raise ValueError(f"{kind} response must contain a non-empty message")
        return AssistantResponse(kind=kind, message=message.strip())

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("tool_call response must contain a non-empty name")

    arguments = data.get("arguments", {})
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise ValueError("tool_call response arguments must be an object")

    return AssistantResponse(kind="tool_call", name=name.strip(), arguments=arguments)


def extract_user_visible_message(content: str) -> str | None:
    """从结构化控制层响应中提取面向用户展示的消息。"""
    try:
        response = parse_assistant_response(content)
    except Exception:
        return None

    if response.kind in {"to_user", "ask_user"}:
        return response.message
    return None
