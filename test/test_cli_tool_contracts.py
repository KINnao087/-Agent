from __future__ import annotations

import inspect
import json
from types import SimpleNamespace
from unittest.mock import patch

from core.application.agent.chat_service import (
    _build_tool_defs,
    _tool_linearize_documents,
    _tool_ls,
    _tool_parse_documents,
    _tool_pdf2pngs,
    _tool_readfile,
    _tool_review_contract_validity,
    _tool_tavliy_search,
    _tool_writefile,
)


TOOL_FUNCTIONS = {
    "pdf2pngs": _tool_pdf2pngs,
    "parse_documents": _tool_parse_documents,
    "linearize_documents": _tool_linearize_documents,
    "tavliy_search": _tool_tavliy_search,
    "review_contract_validity": _tool_review_contract_validity,
    "ls": _tool_ls,
    "readfile": _tool_readfile,
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
