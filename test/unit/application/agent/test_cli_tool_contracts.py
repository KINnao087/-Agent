from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from core.application.agent.tools import (
    TOOLS,
    check_cross_page_seal,
    linearize_contract_documents,
)
from core.domain.contracts import CPSealResult


def test_tools_have_unique_names_and_inferred_schemas() -> None:
    names = [tool.name for tool in TOOLS]
    assert len(names) == len(set(names))
    assert {"review_contract", "review_validity", "check_contract_seals"} <= set(names)
    assert all(tool.args_schema is not None for tool in TOOLS)


def test_linearize_tool_uses_default_output_directory() -> None:
    fake_result = SimpleNamespace(
        ocr_payload={"contract": [{}], "attachments": [], "invoice": []},
        output_paths={"contract": "D:/contracts/linearized_output/contract_linearized.txt"},
    )
    with patch(
        "core.application.agent.tools.linearize_documents",
        return_value=fake_result,
    ) as linearize:
        payload = json.loads(
            linearize_contract_documents.invoke(
                {"file_path": "D:/contracts/contract.pdf"}
            )
        )

    assert payload["contract_pages"] == 1
    assert payload["output_dir"].endswith("linearized_output")
    linearize.assert_called_once()


def test_cross_page_seal_tool_serializes_domain_result() -> None:
    result = CPSealResult(
        status="present",
        page_count=2,
        detected_pages=[1, 2],
        main_edge="right",
        risk_level="low",
    )
    with patch(
        "core.application.agent.tools.check_cpseal_services",
        return_value=result,
    ):
        payload = json.loads(
            check_cross_page_seal.invoke({"input_path": "D:/contracts/pages"})
        )

    assert payload["status"] == "present"
    assert payload["page_count"] == 2
