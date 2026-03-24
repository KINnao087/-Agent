from __future__ import annotations

import os
from typing import Any

from .config import AgentConfig
from .providers import BaseChatProvider, DeepSeekApiProvider


def normalize_provider_name(provider_name: str | None) -> str:
    """把 provider 别名归一化成内部使用的名称。"""
    value = str(provider_name or "api").strip().lower()
    aliases = {
        "api": "api",
        "deepseek_api": "api",
    }
    try:
        return aliases[value]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported provider: {provider_name}. Supported values: api, deepseek_api."
        ) from exc


def build_provider(config: AgentConfig | dict[str, Any]) -> BaseChatProvider:
    """根据配置对象或原始字典构建聊天 provider。"""
    if isinstance(config, dict):
        config = AgentConfig.from_dict(config)

    provider_name = normalize_provider_name(config.provider)
    if provider_name != "api":
        raise ValueError(f"Unsupported provider: {provider_name}")

    api_key = (
        os.environ.get("DEEPSEEK_API_KEY")
        or config.deepseek_api.api_key
        or config.api_key
    )
    if not api_key:
        raise RuntimeError("Missing DeepSeek API key. Set DEEPSEEK_API_KEY or config.api_key.")

    return DeepSeekApiProvider(
        api_key=api_key,
        base_url=config.deepseek_api.base_url,
        temperature=config.deepseek_api.temperature,
    )


def deepseek_chat(
    client: BaseChatProvider,
    model: str,
    tool_defs: list[dict],
    messages: list[dict],
    stream_thinking_callback=None,
):
    """把一次聊天请求转发给当前 provider。"""
    return client.chat(
        model=model,
        tool_defs=tool_defs,
        messages=messages,
        stream_thinking_callback=stream_thinking_callback,
    )
