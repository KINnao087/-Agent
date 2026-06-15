from __future__ import annotations

from unittest.mock import Mock, patch

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from core.infrastructure.ai.config import AIConfigRole
from core.infrastructure.ai.invoke import invoke_structured


class DemoResponse(BaseModel):
    ok: bool


def test_invoke_structured_uses_langchain_model_and_multimodal_messages(tmp_path) -> None:
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"image")
    structured_model = Mock()
    structured_model.invoke.return_value = DemoResponse(ok=True)
    model = Mock()
    model.with_structured_output.return_value = structured_model
    prompt = ChatPromptTemplate.from_messages(
        [("system", "system"), ("human", "{message}")]
    )

    with patch("core.infrastructure.ai.invoke.build_chat_model", return_value=model) as build:
        result = invoke_structured(
            prompt,
            DemoResponse,
            {"message": "review"},
            image_paths=[image_path],
            role=AIConfigRole.VISION,
        )

    assert result.ok is True
    build.assert_called_once_with(
        role=AIConfigRole.VISION,
        enable_thinking=False,
    )
    model.with_structured_output.assert_called_once_with(
        DemoResponse,
        method="function_calling",
    )
    messages = structured_model.invoke.call_args.args[0]
    assert messages[0].content == "system"
    assert messages[1].content[0] == {"type": "text", "text": "review"}
    assert messages[1].content[1]["type"] == "image_url"
    assert messages[1].content[1]["image_url"]["url"].startswith(
        "data:image/png;base64,"
    )
