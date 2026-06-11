from __future__ import annotations

from pathlib import Path

from langchain_openai import ChatOpenAI

from .config import AIConfig, load_ai_config


def build_chat_model(
    config: AIConfig | None = None,
    config_path: str | Path | None = None,
) -> ChatOpenAI:
    settings = config or load_ai_config(config_path)
    return ChatOpenAI(
        model=settings.model,
        api_key=settings.api_key,
        base_url=settings.base_url,
        temperature=settings.temperature,
    )
