from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from core.infrastructure.ai.tasks import run_images_and_get_reply
from core.infrastructure.ai.providers import ChatResult


def test_run_images_and_get_reply_sends_multiple_image_urls() -> None:
    config = SimpleNamespace(base_system="base", model="test-model")
    provider = SimpleNamespace(chat=Mock(return_value=ChatResult(content='{"ok": true}')))

    with (
        patch("core.infrastructure.ai.tasks.load_agent_config", return_value=config),
        patch("core.infrastructure.ai.tasks.build_provider", return_value=provider),
        patch(
            "core.infrastructure.ai.tasks._img2b64_dataurl",
            side_effect=["data:image/png;base64,AAA", "data:image/png;base64,BBB"],
        ),
    ):
        reply = run_images_and_get_reply(
            image_paths=["D:/contracts/page1.png", "D:/contracts/page2.png"],
            user_message="检查骑缝章",
            work_description="你是骑缝章复审助手。",
        )

    assert reply == '{"ok": true}'
    provider.chat.assert_called_once()
    call_kwargs = provider.chat.call_args.kwargs
    assert call_kwargs["model"] == "test-model"
    assert call_kwargs["tool_defs"] == []

    messages = call_kwargs["messages"]
    assert messages[0] == {"role": "system", "content": "base\n\n你是骑缝章复审助手。"}
    user_content = messages[1]["content"]
    assert user_content[0] == {"type": "text", "text": "检查骑缝章"}
    assert user_content[1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,AAA"},
    }
    assert user_content[2] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,BBB"},
    }


def test_run_images_and_get_reply_rejects_empty_image_paths() -> None:
    with pytest.raises(ValueError, match="image_paths must not be empty"):
        run_images_and_get_reply(image_paths=[], user_message="检查骑缝章")
