from __future__ import annotations

import json
from unittest.mock import Mock, patch

from core.application.agent.tools import (
    TOOLS,
    check_contract_seals,
    prepare_contract,
    write_review_report,
)


def test_agent_exposes_business_review_tools_not_low_level_processing_tools() -> None:
    names = {tool.name for tool in TOOLS}

    assert {
        "find_contract_review",
        "prepare_contract",
        "check_basic_info",
        "check_text_integrity",
        "check_contract_seals",
        "check_cross_page_seal",
        "check_contract_authenticity",
        "get_review_status",
        "write_review_report",
        "get_review_result",
        "list_files",
        "read_text_file",
        "read_image",
        "write_text_file",
    } == names
    assert {
        "pdf2pngs",
        "parse_documents",
        "linearize_contract_documents",
        "review_contract",
        "review_validity",
        "web_search",
    }.isdisjoint(names)
    assert len(names) == len(TOOLS)
    assert all(tool.args_schema is not None for tool in TOOLS)


def test_prepare_contract_tool_returns_review_id_from_shared_service() -> None:
    service = Mock()
    service.prepare_contract.return_value = {
        "review_id": "review_123",
        "cached": False,
    }
    with patch(
        "core.application.agent.tools.get_contract_review_service",
        return_value=service,
    ):
        payload = json.loads(
            prepare_contract.invoke(
                {
                    "contract_path": "D:/contracts/contract.pdf",
                    "platform_basic_info": {"contract_no": "HT-1"},
                }
            )
        )

    assert payload["review_id"] == "review_123"
    service.prepare_contract.assert_called_once_with(
        contract_path="D:/contracts/contract.pdf",
        attachments_path="",
        invoice_path="",
        platform_basic_info={"contract_no": "HT-1"},
    )


def test_specialty_and_report_tools_only_require_review_id() -> None:
    service = Mock()
    service.check_contract_seals.return_value = {"seller_seal": {}}
    service.write_review_report.return_value = {
        "overall_status": "passed",
        "markdown_path": "reports/contract_review.md",
    }
    with patch(
        "core.application.agent.tools.get_contract_review_service",
        return_value=service,
    ):
        seal_payload = json.loads(
            check_contract_seals.invoke({"review_id": "review_123"})
        )
        report_payload = json.loads(
            write_review_report.invoke({"review_id": "review_123"})
        )

    assert seal_payload == {"seller_seal": {}}
    assert report_payload["overall_status"] == "passed"
    service.check_contract_seals.assert_called_once_with("review_123")
    service.write_review_report.assert_called_once_with("review_123")
