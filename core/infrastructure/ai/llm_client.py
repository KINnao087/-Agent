from __future__ import annotations

import os
from typing import Any

from .config import AgentConfig
from .providers import ApiProvider, BaseChatProvider


def normalize_provider_name(provider_name: str | None) -> str:
    """把 provider 别名归一化成内部使用的名称。"""
    value = str(provider_name or "api").strip().lower()
    aliases = {
        "api": "api",
    }
    try:
        return aliases[value]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported provider: {provider_name}. Supported values: api."
        ) from exc


def build_provider(config: AgentConfig | dict[str, Any]) -> BaseChatProvider:
    """根据配置对象或原始字典构建聊天 provider。"""
    if isinstance(config, dict):
        config = AgentConfig.from_dict(config)

    provider_name = normalize_provider_name(config.provider)
    if provider_name != "api":
        raise ValueError(f"Unsupported provider: {provider_name}")

    api_key = os.environ.get("AI_API_KEY") or config.api.api_key
    if not api_key:
        raise RuntimeError("Missing API key. Set AI_API_KEY or config.api.api_key.")

    return ApiProvider(
        api_key=api_key,
        base_url=config.api.base_url,
        temperature=config.api.temperature,
    )
