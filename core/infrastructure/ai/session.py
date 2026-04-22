from __future__ import annotations

import os
import platform
import time
from dataclasses import dataclass
from typing import Any

from .assistant_protocol import extract_user_visible_message
from .agent_loop import run_main_loop
from .config import AgentConfig
from .llm_client import build_provider
from .logger import get_logger
from .message_store import append_message, calc_total_tokens
from .providers import BaseChatProvider


@dataclass(slots=True)
class ConversationSession:
    messages: list[dict]
    total_tokens: int
    last_reply: str = ""

    @classmethod
    def from_messages(cls, messages: list[dict], model: str) -> "ConversationSession":
        """基于现有消息构建会话对象并预计算 token 用量。"""
        return cls(messages=list(messages), total_tokens=calc_total_tokens(messages, model))


def sanitize_text(value: Any) -> str:
    """把任意输入转换成可安全存储的 UTF-8 文本。"""
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.encode("utf-8", "replace").decode("utf-8")


def get_last_assistant_text(messages: list[dict]) -> str:
    """返回历史中最近一条非空 assistant 文本。"""
    for message in reversed(messages):
        if message.get("role") != "assistant":
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            structured_text = extract_user_visible_message(content)
            return structured_text if structured_text is not None else content.strip()
    return ""


def preview_text(value: Any, limit: int = 1200) -> str:
    """生成适合写入日志的短文本预览。"""
    text = sanitize_text(value).replace("\r\n", "\n")
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...(truncated, {len(text)} chars total)"


def get_system_info() -> str:
    """收集简洁的运行环境信息供 system 提示使用。"""
    lines = [
        f"OS: {platform.system()}",
        f"Release: {platform.release()}",
        f"Machine: {platform.machine()}",
        f"Processor: {platform.processor()}",
        f"Python: {platform.python_version()}",
    ]
    return "\n".join(lines)


def build_initial_messages(base_system: str, working_directory: str | None = None) -> list[dict]:
    """为新会话构建初始的 system 消息列表。"""
    working_directory = working_directory or os.getcwd()
    full_system = (
        base_system
        + f"\n\nCurrent working directory: {working_directory}\n\nSystem info:\n{get_system_info()}"
    )
    return [{"role": "system", "content": full_system}]


def build_initial_session(
    model: str,
    base_system: str,
    working_directory: str | None = None,
) -> ConversationSession:
    """创建一个带初始 system 上下文的新会话对象。"""
    messages = build_initial_messages(base_system, working_directory=working_directory)
    return ConversationSession.from_messages(messages, model)


class AgentRunner:
    def __init__(
        self,
        config: AgentConfig,
        tools: dict[str, Any] | None = None,
        provider: BaseChatProvider | None = None,
    ):
        """把配置、工具集和 provider 绑定成可复用的运行器。"""
        self.config = config
        self.tools = dict(tools or {})
        self.provider = provider or build_provider(config)

    def new_session(self, working_directory: str | None = None) -> ConversationSession:
        """基于当前配置创建一个新的会话。"""
        return build_initial_session(
            model=self.config.model,
            base_system=self.config.base_system,
            working_directory=working_directory,
        )

    def run(
        self,
        task: str,
        session: ConversationSession | None = None,
        max_steps: int = 18,
        enable_thinking_stream: bool = True,
        echo_output: bool = True,
    ) -> ConversationSession:
        """执行一次用户任务并返回更新后的会话对象。"""
        logger = get_logger("ai-session")
        session = session or self.new_session()

        messages = list(session.messages)
        total_tokens = session.total_tokens or calc_total_tokens(messages, self.config.model)

        messages, total_tokens = append_message(
            messages,
            {"role": "user", "content": sanitize_text(task)},
            total_tokens,
            keep_last=self.config.keep_last,
            model=self.config.model,
            auto_trim=True,
        )

        start = time.perf_counter()
        logger.info(
            "Start task, max_steps={}, stream={}, existing_messages={}, total_tokens={}",
            max_steps,
            enable_thinking_stream,
            len(messages),
            total_tokens,
        )

        step, content, messages, total_tokens = run_main_loop(
            client=self.provider,
            model=self.config.model,
            tool_defs=self.config.tool_defs,
            tools=self.tools,
            keep_last=self.config.keep_last,
            max_steps=max_steps,
            enable_thinking_stream=enable_thinking_stream,
            messages=messages,
            total_tokens=total_tokens,
            echo_output=echo_output,
        )

        elapsed = time.perf_counter() - start
        last_reply = get_last_assistant_text(messages) or content
        logger.info("Task completed in {:.3f}s after {} step(s)", elapsed, step)
        logger.info("Assistant final preview: {}", preview_text(last_reply))

        return ConversationSession(messages=messages, total_tokens=total_tokens, last_reply=last_reply)

    def run_and_get_reply(
        self,
        task: str,
        session: ConversationSession | None = None,
        max_steps: int = 18,
        enable_thinking_stream: bool = False,
    ) -> tuple[str, ConversationSession]:
        """执行一次任务并同时返回最终文本和更新后的会话。"""
        session = self.run(
            task=task,
            session=session,
            max_steps=max_steps,
            enable_thinking_stream=enable_thinking_stream,
            echo_output=False,
        )
        return session.last_reply or get_last_assistant_text(session.messages), session
