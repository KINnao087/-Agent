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
    if enable_thinking is not None:
        model_name = settings.model.lower()
        if "qwen" in model_name:
            kwargs["extra_body"] = {"enable_thinking": enable_thinking}
        elif "deepseek" in model_name:
            kwargs["extra_body"] = {
                "thinking": {
                    "type": "enabled" if enable_thinking else "disabled"
                }
            }
    return ChatOpenAI(
        **kwargs,
    )
