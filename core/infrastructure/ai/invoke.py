from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, TypeVar

from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from .config import AIConfigRole
from .model import build_chat_model

OutputT = TypeVar("OutputT", bound=BaseModel)


def image_data_url(image_path: str | Path) -> str:
    path = Path(image_path)
    mime_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "image/png")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _render_messages(
    prompt: ChatPromptTemplate,
    values: dict[str, Any],
    image_paths: list[str | Path] | None = None,
) -> list[BaseMessage]:
    messages = prompt.invoke(values).to_messages()
    if not image_paths:
        return messages

    user_message = messages[-1]
    text = user_message.content if isinstance(user_message.content, str) else str(user_message.content)
    user_message.content = [
        {"type": "text", "text": text},
        *[
            {
                "type": "image_url",
                "image_url": {"url": image_data_url(image_path)},
            }
            for image_path in image_paths
        ],
    ]
    return messages


def invoke_text(
    prompt: ChatPromptTemplate,
    values: dict[str, Any],
    image_paths: list[str | Path] | None = None,
    *,
    role: AIConfigRole = AIConfigRole.MAIN,
) -> str:
    response = build_chat_model(role=role).invoke(
        _render_messages(prompt, values, image_paths)
    )
    return str(response.content)


def invoke_structured(
    prompt: ChatPromptTemplate,
    schema: type[OutputT],
    values: dict[str, Any],
    image_paths: list[str | Path] | None = None,
    *,
    role: AIConfigRole,
) -> OutputT:
    model = build_chat_model(
        role=role,
        enable_thinking=False,
    ).with_structured_output(
        schema,
        method="function_calling",
    )
    response = model.invoke(_render_messages(prompt, values, image_paths))
    if response is None:
        raise RuntimeError(
            f"structured model returned no {schema.__name__} payload"
        )
    return response if isinstance(response, schema) else schema.model_validate(response)
