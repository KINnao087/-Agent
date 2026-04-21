from __future__ import annotations

import inspect
import json
from types import SimpleNamespace
from unittest.mock import patch

from core.application.agent.chat_service import (
    _build_tool_defs,
    _tool_check_contract,
    _tool_linearize_documents,
    _tool_ls,
    _tool_parse_documents,
    _tool_pdf2pngs,
    _tool_readfile,
    _tool_readimage,
    _tool_review_contract_validity,
    _tool_tavliy_search,
    _tool_writefile,
)
from core.infrastructure.ai.agent_loop import _handle_tool_calls, handle_tool_call
from core.infrastructure.ai.message_store import trim_messages
from core.infrastructure.ai.providers import ToolCall, ToolFunction


TOOL_FUNCTIONS = {
    "pdf2pngs": _tool_pdf2pngs,
    "parse_documents": _tool_parse_documents,
    "linearize_documents": _tool_linearize_documents,
    "check_contract": _tool_check_contract,
    "tavliy_search": _tool_tavliy_search,
    "review_contract_validity": _tool_review_contract_validity,
    "ls": _tool_ls,
    "readfile": _tool_readfile,
    "readimage": _tool_readimage,
    "writefile": _tool_writefile,
}


def test_tool_def_parameters_are_accepted_by_adapters() -> None:
    for tool_def in _build_tool_defs():
        name = tool_def["function"]["name"]
        properties = set(tool_def["function"]["parameters"]["properties"])
        accepted_parameters = set(inspect.signature(TOOL_FUNCTIONS[name]).parameters)

        assert properties <= accepted_parameters


def test_linearize_documents_accepts_directory_aliases() -> None:
    fake_result = SimpleNamespace(
        ocr_payload={"contract": [object()], "attachments": [], "invoice": []},
        linearized_document={
            "contract_text": "contract text",
            "attachment_text": "",
            "invoice_text": "",
        },
        output_paths={"contract": "contract_linearized.txt"},
    )

    with patch(
        "core.application.agent.chat_service.linearize_documents",
        return_value=fake_result,
    ) as linearize:
        result = _tool_linearize_documents(
            input_directory="D:/contracts/pages",
            output_directory="D:/contracts/pages",
        )

    assert result["ok"] is True
    linearize.assert_called_once_with(
        file_path="D:/contracts/pages",
        output_dir="D:/contracts/pages",
        attachments_path=None,
        invoice_path=None,
    )
    payload = json.loads(result["output"])
    assert payload["file_path"] == "D:/contracts/pages"


def test_readimage_adapter_attaches_image_url_without_inline_payload() -> None:
    with patch(
        "core.application.agent.chat_service.sys_readimage",
        return_value={
            "path": "D:/contracts/page.png",
            "name": "page.png",
            "mime_type": "image/png",
            "size": 123,
            "base64": "AAAA",
            "data_url": "data:image/png;base64,AAAA",
        },
    ):
        result = _tool_readimage(path="D:/contracts/page.png")

    payload = json.loads(result["output"])
    assert result["ok"] is True
    assert result["image_url"] == "data:image/png;base64,AAAA"
    assert result["image_name"] == "page.png"
    assert payload["image_url_attached"] is True
    assert "data:image/png;base64,AAAA" not in result["output"]
    assert '"base64"' not in result["output"]


def test_image_tool_result_appends_multimodal_image_url_message() -> None:
    tool_call = ToolCall(
        id="call_image",
        function=ToolFunction(
            name="readimage",
            arguments=json.dumps({"path": "D:/contracts/page.png"}),
        ),
    )

    def fake_readimage(path: str) -> dict:
        return {
            "ok": True,
            "output": json.dumps({"name": "page.png", "image_url_attached": True}),
            "image_url": "data:image/png;base64,AAAA",
            "image_name": "page.png",
            "image_path": path,
            "image_mime_type": "image/png",
        }

    messages, total_tokens = handle_tool_call(
        tool_call=tool_call,
        name="readimage",
        args=tool_call.function.arguments,
        tools={"readimage": fake_readimage},
        messages=[],
        total_tokens=0,
        keep_last=100000,
        model="gpt-4o",
    )

    assert total_tokens > 0
    assert messages[0]["role"] == "tool"
    assert messages[0]["content"] == '{"name": "page.png", "image_url_attached": true}'
    assert messages[1]["role"] == "user"
    assert messages[1]["content"][0]["type"] == "text"
    assert messages[1]["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,AAAA"},
    }


def test_native_multi_tool_calls_defer_image_messages_until_tool_results_complete() -> None:
    tool_calls = [
        ToolCall(
            id="call_image",
            function=ToolFunction(
                name="readimage",
                arguments=json.dumps({"path": "D:/contracts/page.png"}),
            ),
        ),
        ToolCall(
            id="call_ls",
            function=ToolFunction(
                name="ls",
                arguments=json.dumps({"path": "D:/contracts"}),
            ),
        ),
    ]

    def fake_readimage(path: str) -> dict:
        return {
            "ok": True,
            "output": json.dumps({"name": "page.png", "image_url_attached": True}),
            "image_url": "data:image/png;base64,AAAA",
            "image_name": "page.png",
            "image_path": path,
            "image_mime_type": "image/png",
        }

    def fake_ls(path: str) -> dict:
        return {"ok": True, "output": json.dumps({"path": path, "entries": []})}

    messages, _ = _handle_tool_calls(
        tool_calls=tool_calls,
        messages=[],
        total_tokens=0,
        keep_last=100000,
        model="gpt-4o",
        message=SimpleNamespace(content="", tool_calls=tool_calls),
        tools={"readimage": fake_readimage, "ls": fake_ls},
    )

    assert [message["role"] for message in messages] == ["assistant", "tool", "tool", "user"]
    assert messages[1]["tool_call_id"] == "call_image"
    assert messages[2]["tool_call_id"] == "call_ls"
    assert messages[3]["content"][1]["type"] == "image_url"


def test_trim_messages_preserves_latest_user_for_provider_compatibility() -> None:
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "please call a tool"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_big",
                    "type": "function",
                    "function": {"name": "readfile", "arguments": '{"path":"big.txt"}'},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_big",
            "name": "readfile",
            "content": "x" * 2000,
        },
    ]

    trimmed = trim_messages(messages, keep_last=100, model="gpt-4o")

    roles = [message["role"] for message in trimmed]
    assert "user" in roles
    assert roles[-2:] == ["assistant", "tool"]
