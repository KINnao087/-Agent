from __future__ import annotations

from pathlib import Path

from langchain_openai import ChatOpenAI

from .config import AIConfig, AIConfigRole, load_ai_config


def build_chat_model(
    config: AIConfig | None = None,
    config_path: str | Path | None = None,
    *,
    role: AIConfigRole = AIConfigRole.MAIN,
    enable_thinking: bool | None = None,
) -> ChatOpenAI:
    settings = config or load_ai_config(config_path, role=role)
    kwargs = {
        "model": settings.model,
        "api_key": settings.api_key,
        "base_url": settings.base_url,
        "temperature": settings.temperature,
    }
    if enable_thinking is not None and "qwen" in settings.model.lower():
        kwargs["extra_body"] = {"enable_thinking": enable_thinking}
    return ChatOpenAI(
        **kwargs,
    )
