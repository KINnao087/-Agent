from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from typing import Any

from .logger import get_logger
from .message_store import append_message
from .providers import ToolCall, ToolFunction

CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)
FINAL_RE = re.compile(r"<final>\s*(.*?)\s*</final>", re.S)
EDIT_INTENT_RE = re.compile(
    r"(\bedit\b|\bmodify\b|\bchange\b|\bupdate\b|\brewrite\b|\brefactor\b|\bfix\b|\bcomment\b|修改|更新|重构|修复|注释|回写)",
    re.I,
)
QUESTION_INTENT_RE = re.compile(r"(\bhow\b|\bwhy\b|\?|怎么|如何|为什么)", re.I)
WRITE_ENFORCEMENT_TEXT = (
    "The user requested a file modification. You must use a tool_call to apply the change. "
    "If write_file is available, use write_file instead of pasting modified code directly."
)
INVALID_TOOL_CALL_JSON_TEXT = (
    "Your previous <tool_call> JSON was invalid. Return exactly one corrected <tool_call> tag with strict valid JSON only. "
    "Escape all string values correctly. If you call write_file, the arguments.content field must be a valid JSON string with escaped newlines and quotes."
)

ToolFn = Callable[..., Any]
ToolMap = Mapping[str, ToolFn]


def _preview_text(value: object, limit: int = 300) -> str:
    """生成适合日志和报错展示的单行预览文本。"""
    text = "" if value is None else str(value)
    text = text.replace("\r", "\\r").replace("\n", "\\n")
    return text if len(text) <= limit else text[:limit] + "...(truncated)"


def parse_tool_call(content: str):
    """解析 assistant 文本中内嵌的一个工具调用标签。"""
    match = CALL_RE.search(content or "")
    if not match:
        return None

    payload = match.group(1)
    try:
        obj = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Invalid tool_call JSON at "
            f"line {exc.lineno} column {exc.colno}: {exc.msg}. "
            f"Payload preview: {_preview_text(payload, 500)}"
        ) from exc

    name = obj.get("name")
    if not name:
        raise ValueError(
            f"tool_call is missing name. Payload preview: {_preview_text(payload, 500)}"
        )
    return name, obj.get("arguments", {})


def parse_final(content: str):
    """提取带 final 标签的最终回复内容。"""
    match = FINAL_RE.search(content or "")
    return match.group(1) if match else None


def _latest_user_text(messages: list[dict]) -> str:
    """返回最近一条用户消息的纯文本内容。"""
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content")
            return content if isinstance(content, str) else str(content or "")
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
    return "write_file" in _tool_names(tool_defs)


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
        return {"ok": ok, "output": "" if output is None else str(output)}
    if result is None:
        return {"ok": True, "output": ""}
    return {"ok": True, "output": str(result)}


def handle_tool_call(
    tool_call: ToolCall,
    name: str,
    args: dict | str,
    tools: ToolMap,
    messages: list[dict],
    total_tokens: int,
    keep_last: int,
    model: str,
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
            logger.info(
                "Model requested {} tool call(s), assistant content preview: {}",
                len(tool_calls),
                _preview_text(getattr(message, "content", "") or ""),
            )

            messages, total_tokens = append_message(
                messages,
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments,
                            },
                        }
                        for tool_call in tool_calls
                    ],
                },
                total_tokens,
                keep_last=keep_last,
                model=model,
                auto_trim=True,
            )

            tool_call = tool_calls[0]
            name = tool_call.function.name
            args = tool_call.function.arguments or "{}"
            logger.info("Executing first tool call: {}", name)
            messages, total_tokens = handle_tool_call(
                tool_call,
                name,
                args,
                tools,
                messages,
                total_tokens,
                keep_last=keep_last,
                model=model,
            )
            continue

        content = (getattr(message, "content", None) or "").strip()
        logger.info("Model content preview at step {}: {}", step, _preview_text(content))

        if content and _user_request_requires_file_write(messages, tool_defs):
            logger.warning(
                "Edit request returned direct content instead of a write tool call; enforcing retry"
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

        messages, total_tokens = append_message(
            messages,
            {"role": "assistant", "content": content},
            total_tokens,
            keep_last=keep_last,
            model=model,
            auto_trim=True,
        )

        final_text = parse_final(content)
        if final_text is not None:
            logger.info("Task completed with final tag")
            logger.info("Final tag content preview: {}", _preview_text(final_text))
            if echo_output:
                print(final_text)
            return step, content, messages, total_tokens

        try:
            maybe_tool_call = parse_tool_call(content)
        except ValueError as exc:
            logger.error("Malformed tagged tool call: {}", str(exc))
            messages, total_tokens = append_message(
                messages,
                {"role": "system", "content": INVALID_TOOL_CALL_JSON_TEXT},
                total_tokens,
                keep_last=keep_last,
                model=model,
                auto_trim=True,
            )
            continue

        if maybe_tool_call:
            name, args = maybe_tool_call
            tagged_call = ToolCall(
                id=f"tagged_call_{step}",
                function=ToolFunction(
                    name=name,
                    arguments=json.dumps(args, ensure_ascii=False) if isinstance(args, dict) else str(args),
                ),
            )
            messages, total_tokens = handle_tool_call(
                tagged_call,
                name,
                args,
                tools,
                messages,
                total_tokens,
                keep_last=keep_last,
                model=model,
            )
            continue

        if content:
            logger.info("Returning assistant content without final tag: {}", _preview_text(content))
            if echo_output:
                print(content)
            return step, content, messages, total_tokens

        logger.warning("Model returned no usable content; ending task")
        return step, content, messages, total_tokens

    return max_steps, "", messages, total_tokens
