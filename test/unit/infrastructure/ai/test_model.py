from __future__ import annotations

from unittest.mock import Mock, patch

from core.infrastructure.ai.config import AIConfig, AIConfigRole
from core.infrastructure.ai.model import build_chat_model


def test_build_chat_model_can_disable_thinking_for_structured_tasks() -> None:
    config = AIConfig(
        model="qwen3.5-flash",
        base_url="https://example.com/v1",
        api_key="test-key",
    )

    with patch("core.infrastructure.ai.model.ChatOpenAI") as chat_openai:
        build_chat_model(config, enable_thinking=False)

    assert chat_openai.call_args.kwargs["extra_body"] == {
        "enable_thinking": False
    }


def test_build_chat_model_leaves_main_agent_thinking_setting_unchanged() -> None:
    config = AIConfig(
        model="qwen3.5-flash",
        base_url="https://example.com/v1",
        api_key="test-key",
    )

    with patch("core.infrastructure.ai.model.ChatOpenAI") as chat_openai:
        build_chat_model(config)

    assert "extra_body" not in chat_openai.call_args.kwargs


def test_build_chat_model_does_not_send_qwen_thinking_flag_to_deepseek() -> None:
    config = AIConfig(
        model="deepseek-pro",
        base_url="https://deepseek.example.com/v1",
        api_key="test-key",
    )

    with patch("core.infrastructure.ai.model.ChatOpenAI") as chat_openai:
        build_chat_model(config, enable_thinking=False)

    assert "extra_body" not in chat_openai.call_args.kwargs


def test_build_chat_model_loads_requested_role() -> None:
    config = AIConfig(
        model="deepseek-pro",
        base_url="https://text.example.com/v1",
        api_key="text-key",
    )

    with (
        patch(
            "core.infrastructure.ai.model.load_ai_config",
            return_value=config,
        ) as load,
        patch(
            "core.infrastructure.ai.model.ChatOpenAI",
            return_value=Mock(),
        ),
    ):
        build_chat_model(role=AIConfigRole.TEXT)

    load.assert_called_once_with(None, role=AIConfigRole.TEXT)
