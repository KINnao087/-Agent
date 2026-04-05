from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable


@dataclass(slots=True)
class ToolFunction:
    name: str
    arguments: str


@dataclass(slots=True)
class ToolCall:
    id: str
    function: ToolFunction


@dataclass(slots=True)
class ChatResult:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    reasoning_content: str = ""


class BaseChatProvider(ABC):
    @abstractmethod
    def chat(
        self,
        model: str,
        tool_defs: list[dict],
        messages: list[dict],
        stream_thinking_callback: Callable[[str], None] | None = None,
    ) -> ChatResult:
        """执行一次对话请求并返回文本及工具调用结果。"""
        raise NotImplementedError
