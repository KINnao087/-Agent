from __future__ import annotations

from typing import Callable

from ..logger import (
    end_thinking_stream,
    get_logger,
    start_thinking_stream,
    stream_thinking,
)
from .base import BaseChatProvider, ChatResult, ToolCall, ToolFunction


class DeepSeekApiProvider(BaseChatProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        temperature: float = 0.2,
    ):
        """使用兼容 OpenAI 的 SDK 初始化 API provider。"""
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._temperature = temperature

    def chat(
        self,
        model: str,
        tool_defs: list[dict],
        messages: list[dict],
        stream_thinking_callback: Callable[[str], None] | None = None,
    ) -> ChatResult:
        """发送一次对话请求并把返回结果整理成统一结构。"""
        logger = get_logger("ai-provider")
        is_stream = bool(stream_thinking_callback)

        try:
            if not is_stream:
                response = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=tool_defs,
                    tool_choice="auto",
                    temperature=self._temperature,
                    stream=False,
                )
                message = response.choices[0].message
                tool_calls = [
                    ToolCall(
                        id=tool_call.id,
                        function=ToolFunction(
                            name=tool_call.function.name,
                            arguments=tool_call.function.arguments or "{}",
                        ),
                    )
                    for tool_call in (getattr(message, "tool_calls", None) or [])
                ]
                return ChatResult(
                    content=getattr(message, "content", "") or "",
                    tool_calls=tool_calls,
                    reasoning_content=getattr(message, "reasoning_content", "") or "",
                )

            start_thinking_stream()
            response = self._client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tool_defs,
                tool_choice="auto",
                temperature=self._temperature,
                stream=True,
            )

            content_parts: list[str] = []
            reasoning_parts: list[str] = []
            tool_call_chunks: dict[int, dict[str, str | None]] = {}

            for chunk in response:
                choice = chunk.choices[0]
                delta = choice.delta

                reasoning_chunk = getattr(delta, "reasoning_content", None)
                if reasoning_chunk:
                    reasoning_parts.append(reasoning_chunk)
                    stream_thinking(reasoning_chunk)
                    stream_thinking_callback(reasoning_chunk)

                content_chunk = getattr(delta, "content", None)
                if content_chunk:
                    content_parts.append(content_chunk)

                for tool_call in getattr(delta, "tool_calls", None) or []:
                    index = getattr(tool_call, "index", 0)
                    entry = tool_call_chunks.setdefault(
                        index,
                        {"id": getattr(tool_call, "id", None), "name": "", "arguments": ""},
                    )
                    if getattr(tool_call, "id", None):
                        entry["id"] = tool_call.id
                    function = getattr(tool_call, "function", None)
                    if not function:
                        continue
                    if getattr(function, "name", None):
                        entry["name"] += function.name
                    if getattr(function, "arguments", None):
                        entry["arguments"] += function.arguments

            tool_calls = [
                ToolCall(
                    id=(entry["id"] or f"call_{index}"),
                    function=ToolFunction(
                        name=str(entry["name"] or ""),
                        arguments=str(entry["arguments"] or "{}"),
                    ),
                )
                for index, entry in sorted(tool_call_chunks.items())
            ]

            return ChatResult(
                content="".join(content_parts),
                tool_calls=tool_calls,
                reasoning_content="".join(reasoning_parts),
            )
        except Exception as exc:
            logger.error("DeepSeek API call failed: {}", str(exc))
            raise
        finally:
            if is_stream:
                end_thinking_stream()
