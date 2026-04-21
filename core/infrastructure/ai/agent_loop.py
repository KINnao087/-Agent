from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from typing import Any

from .assistant_protocol import AssistantResponse, parse_assistant_response
from .logger import get_logger
from .message_store import append_message
from .providers import ToolCall, ToolFunction

EDIT_INTENT_RE = re.compile(
    r"(\bedit\b|\bmodify\b|\bchange\b|\bupdate\b|\brewrite\b|\brefactor\b|\bfix\b|\bcomment\b|修改|更新|重构|修复|注释|回写)",
    re.I,
)
QUESTION_INTENT_RE = re.compile(r"(\bhow\b|\bwhy\b|\?|怎么|如何|为什么)", re.I)
WRITE_ENFORCEMENT_TEXT = (
    "The user requested a file modification. You must use a tool_call to apply the change. "
    "If writefile or write_file is available, use it instead of pasting modified code directly."
)
STRUCTURED_RESPONSE_PROTOCOL_TEXT = (
    "When tools are available, every non-tool assistant reply must be a single JSON object only. "
    'Use {"type":"to_user","message":"..."} to answer the user, '
    'use {"type":"ask_user","message":"..."} to ask for missing information, '
    'and use a native tool call whenever possible. '
    'If native tool calls are unavailable, use {"type":"tool_call","name":"tool_name","arguments":{...}}. '
    "Do not output markdown, prose outside JSON, or status narration."
)
INVALID_STRUCTURED_RESPONSE_TEXT = (
    "Your previous reply did not follow the required JSON response protocol. "
    'Return exactly one JSON object with one of these forms: '
    '{"type":"to_user","message":"..."}, '
    '{"type":"ask_user","message":"..."}, '
    '{"type":"tool_call","name":"tool_name","arguments":{...}}.'
)

ToolFn = Callable[..., Any]
ToolMap = Mapping[str, ToolFn]


def _preview_text(value: object, limit: int = 300) -> str:
    """生成适合日志和报错展示的单行预览文本。"""
    text = "" if value is None else str(value)
    text = text.replace("\r", "\\r").replace("\n", "\\n")
    return text if len(text) <= limit else text[:limit] + "...(truncated)"


def _content_to_text(content: Any) -> str:
    """Extract text from string or multimodal message content without dumping image data."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                item_type = item.get("type")
                if item_type == "text":
                    parts.append(str(item.get("text", "")))
                elif item_type == "image_url":
                    parts.append("[image_url]")
                else:
                    parts.append(str({key: value for key, value in item.items() if key != "image_url"}))
            elif item is not None:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    return "" if content is None else str(content)


def _latest_user_text(messages: list[dict]) -> str:
    """返回最近一条用户消息的纯文本内容。"""
    for message in reversed(messages):
        if message.get("role") == "user":
            return _content_to_text(message.get("content"))
    return ""


def _tool_names(tool_defs: list[dict]) -> set[str]:
    """从工具定义列表中收集所有工具名称。"""
    names: set[str] = set()
    for tool in tool_defs or []:
        function = tool.get("function") if isinstance(tool, dict) else None
        name = function.get("name") if isinstance(function, dict) else None
        if name:
            names.add(str(name))
    return names


def _user_request_requires_file_write(messages: list[dict], tool_defs: list[dict]) -> bool:
    """判断当前用户请求是否应当通过写文件工具来完成。"""
    latest_user = _latest_user_text(messages).strip()
    if not latest_user:
        return False
    if not EDIT_INTENT_RE.search(latest_user):
        return False
    if QUESTION_INTENT_RE.search(latest_user):
        return False
    names = _tool_names(tool_defs)
    return "writefile" in names or "write_file" in names


def _has_system_note(messages: list[dict], note: str) -> bool:
    """检查历史消息中是否已经存在指定的 system 提示。"""
    return any(
        message.get("role") == "system" and message.get("content") == note
        for message in messages
    )


def _normalize_tool_result(result: Any) -> dict[str, Any]:
    """把任意工具返回值规整成统一的结果结构。"""
    if isinstance(result, dict):
        ok = bool(result.get("ok", "error" not in result))
        output = result.get("output")
        if output is None:
            output = result.get("error", "")
        normalized: dict[str, Any] = {"ok": ok, "output": "" if output is None else str(output)}
        image_url = result.get("image_url") or result.get("data_url")
        if image_url:
            normalized["image_url"] = str(image_url)
        image_name = result.get("image_name") or result.get("name")
        if image_name:
            normalized["image_name"] = str(image_name)
        image_path = result.get("image_path") or result.get("path")
        if image_path:
            normalized["image_path"] = str(image_path)
        image_mime_type = result.get("image_mime_type") or result.get("mime_type")
        if image_mime_type:
            normalized["image_mime_type"] = str(image_mime_type)
        return normalized
    if result is None:
        return {"ok": True, "output": ""}
    return {"ok": True, "output": str(result)}


def _build_image_user_message(tool_name: str, result: dict[str, Any]) -> dict[str, Any] | None:
    """Create a multimodal user message for image data returned by a tool."""
    image_url = str(result.get("image_url") or "").strip()
    if not image_url:
        return None

    image_name = str(result.get("image_name") or f"{tool_name}_image")
    image_path = str(result.get("image_path") or "")
    image_mime_type = str(result.get("image_mime_type") or "")
    text = (
        f"Tool {tool_name} returned image data for {image_name}"
        f"{f' ({image_mime_type})' if image_mime_type else ''}. "
        "Use the attached image_url as the image input. Do not treat encoded image data as ordinary prose."
    )
    if image_path:
        text += f" Source path: {image_path}"

    return {
        "role": "user",
        "content": [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": image_url}},
        ],
    }


def _append_assistant_message(
    messages: list[dict],
    total_tokens: int,
    keep_last: int,
    model: str,
    content: str,
    tool_calls: list[ToolCall] | None = None,
) -> tuple[list[dict], int]:
    """把 assistant 消息追加到历史中。"""
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in tool_calls
        ]

    return append_message(
        messages,
        message,
        total_tokens,
        keep_last=keep_last,
        model=model,
        auto_trim=True,
    )


def handle_tool_call(
    tool_call: ToolCall,
    name: str,
    args: dict | str,
    tools: ToolMap,
    messages: list[dict],
    total_tokens: int,
    keep_last: int,
    model: str,
    image_messages: list[dict[str, Any]] | None = None,
):
    """执行一次工具调用并把结果追加回消息历史。"""
    logger = get_logger("ai-loop")

    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError as exc:
            result = {
                "ok": False,
                "output": (
                    f"invalid tool call arguments for {name}: line {exc.lineno} column {exc.colno}: {exc.msg}. "
                    f"Arguments preview: {_preview_text(args, 500)}"
                ),
            }
            logger.error("Malformed tool call args for {}: {}", name, result["output"])
            messages, total_tokens = append_message(
                messages,
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": result["output"],
                },
                total_tokens,
                keep_last=keep_last,
                model=model,
                auto_trim=True,
            )
            return messages, total_tokens

    if not isinstance(args, dict):
        result = {"ok": False, "output": f"tool call arguments for {name} must decode to an object"}
        logger.error("Malformed tool call args for {}: {}", name, result["output"])
        messages, total_tokens = append_message(
            messages,
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": name,
                "content": result["output"],
            },
            total_tokens,
            keep_last=keep_last,
            model=model,
            auto_trim=True,
        )
        return messages, total_tokens

    logger.info(
        "Tool call args for {}: {}",
        name,
        _preview_text(json.dumps(args, ensure_ascii=False)),
    )

    if name not in tools:
        result = {"ok": False, "output": f"unknown tool: {name}"}
        logger.error("Unknown tool: {}", name)
    else:
        logger.info("Call tool: {}", name)
        try:
            result = _normalize_tool_result(tools[name](**args))
        except Exception as exc:
            result = {"ok": False, "output": f"{type(exc).__name__}: {exc}"}
            logger.error("Tool {} raised an exception: {}", name, result["output"])

    if result.get("ok"):
        logger.info("Tool {} succeeded", name)
    else:
        logger.error("Tool {} failed: {}", name, result.get("output", ""))
    logger.info("Tool {} output preview: {}", name, _preview_text(result.get("output", "")))

    messages, total_tokens = append_message(
        messages,
        {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": name,
            "content": result.get("output", ""),
        },
        total_tokens,
        keep_last=keep_last,
        model=model,
        auto_trim=True,
    )
    image_message = _build_image_user_message(name, result)
    if image_message is not None:
        if image_messages is None:
            messages, total_tokens = append_message(
                messages,
                image_message,
                total_tokens,
                keep_last=keep_last,
                model=model,
                auto_trim=True,
            )
        else:
            image_messages.append(image_message)
        logger.info(
            "Tool {} image result attached as image_url, source={}",
            name,
            result.get("image_path") or result.get("image_name") or "",
        )
    return messages, total_tokens


def _build_synthetic_tool_call(response: AssistantResponse, step: int) -> ToolCall:
    """把 JSON 形式的 tool_call 响应转成内部统一的 ToolCall 对象。"""
    return ToolCall(
        id=f"json_tool_call_{step}",
        function=ToolFunction(
            name=response.name,
            arguments=json.dumps(response.arguments, ensure_ascii=False),
        ),
    )

def _handle_tool_calls(tool_calls: list[ToolCall], messages: list[dict], total_tokens: int, keep_last: int, model, message, tools: ToolMap):
    logger = get_logger("ai-tool-calls")
    logger.info(
        "Model requested {} tool call(s), assistant content preview: {}",
        len(tool_calls),
        _preview_text(getattr(message, "content", "") or ""),
    )
    messages, total_tokens = _append_assistant_message(
        messages,
        total_tokens,
        keep_last=keep_last,
        model=model,
        content=message.content or "",
        tool_calls=tool_calls,
    )

    deferred_image_messages: list[dict[str, Any]] = []
    for tool_call in tool_calls:
        name = tool_call.function.name
        args = tool_call.function.arguments or "{}"
        logger.info("Executing tool call: {}", name)
        messages, total_tokens = handle_tool_call(
            tool_call,
            name,
            args,
            tools,
            messages,
            total_tokens,
            keep_last=keep_last,
            model=model,
            image_messages=deferred_image_messages,
        )

    for image_message in deferred_image_messages:
        messages, total_tokens = append_message(
            messages,
            image_message,
            total_tokens,
            keep_last=keep_last,
            model=model,
            auto_trim=True,
        )
    return messages, total_tokens


def run_main_loop(
    client,
    model: str,
    tool_defs: list[dict],
    tools: ToolMap,
    keep_last: int,
    max_steps: int,
    enable_thinking_stream: bool,
    messages: list[dict],
    total_tokens: int,
    echo_output: bool = True,
):
    """驱动主循环直到完成回复、触发工具或达到步数上限。"""
    logger = get_logger("ai-loop")

    for step in range(1, max_steps + 1):
        logger.info("Agent loop step {} start, message_count={}", step, len(messages))
        thinking_callback = (lambda chunk: None) if enable_thinking_stream else None
        message = client.chat(
            model=model,
            tool_defs=tool_defs,
            messages=messages,
            stream_thinking_callback=thinking_callback,
        )

        tool_calls = getattr(message, "tool_calls", None) or []
        if tool_calls:
            messages, total_tokens = _handle_tool_calls(
                tool_calls,
                messages,
                total_tokens,
                keep_last,
                model,
                message,
                tools,
            )
            continue

        content = (getattr(message, "content", None) or "").strip()
        logger.info("Model content preview at step {}: {}", step, _preview_text(content))

        if tool_defs:
            if not content:
                logger.warning("Model returned empty assistant content while tools are enabled")
                messages, total_tokens = append_message(
                    messages,
                    {"role": "system", "content": INVALID_STRUCTURED_RESPONSE_TEXT},
                    total_tokens,
                    keep_last=keep_last,
                    model=model,
                    auto_trim=True,
                )
                continue

            try:
                structured_response = parse_assistant_response(content)
            except ValueError as exc:
                logger.warning("Invalid structured assistant response: {}", str(exc))
                if not _has_system_note(messages, STRUCTURED_RESPONSE_PROTOCOL_TEXT):
                    messages, total_tokens = append_message(
                        messages,
                        {"role": "system", "content": STRUCTURED_RESPONSE_PROTOCOL_TEXT},
                        total_tokens,
                        keep_last=keep_last,
                        model=model,
                        auto_trim=True,
                    )
                messages, total_tokens = append_message(
                    messages,
                    {"role": "system", "content": INVALID_STRUCTURED_RESPONSE_TEXT},
                    total_tokens,
                    keep_last=keep_last,
                    model=model,
                    auto_trim=True,
                )
                continue

            if (
                structured_response.kind != "tool_call"
                and _user_request_requires_file_write(messages, tool_defs)
            ):
                logger.warning(
                    "Edit request returned a user-facing message instead of a write tool call; enforcing retry"
                )
                if not _has_system_note(messages, WRITE_ENFORCEMENT_TEXT):
                    messages, total_tokens = append_message(
                        messages,
                        {"role": "system", "content": WRITE_ENFORCEMENT_TEXT},
                        total_tokens,
                        keep_last=keep_last,
                        model=model,
                        auto_trim=True,
                    )
                    continue

            messages, total_tokens = _append_assistant_message(
                messages,
                total_tokens,
                keep_last=keep_last,
                model=model,
                content=content,
            )

            if structured_response.kind == "tool_call":
                tagged_call = _build_synthetic_tool_call(structured_response, step)
                messages, total_tokens = handle_tool_call(
                    tagged_call,
                    structured_response.name,
                    structured_response.arguments,
                    tools,
                    messages,
                    total_tokens,
                    keep_last=keep_last,
                    model=model,
                )
                continue

            display_text = structured_response.message
            logger.info(
                "Returning structured assistant message at step {}: {}",
                step,
                _preview_text(display_text),
            )
            if echo_output:
                print(display_text)
            return step, display_text, messages, total_tokens

        messages, total_tokens = append_message(
            messages,
            {"role": "assistant", "content": content},
            total_tokens,
            keep_last=keep_last,
            model=model,
            auto_trim=True,
        )

        if content:
            logger.info("Returning assistant content without tools: {}", _preview_text(content))
            if echo_output:
                print(content)
            return step, content, messages, total_tokens

        logger.warning("Model returned no usable content; ending task")
        return step, content, messages, total_tokens

    return max_steps, "", messages, total_tokens
