from __future__ import annotations

from unittest.mock import patch

from core.domain.contracts.models import ContractBasicInfo
from core.infrastructure.ai.prompts import BASIC_INFO_PROMPT
from core.infrastructure.contracts.basic_info_extractor import extract_contract_basic_info


def test_extract_contract_basic_info_uses_structured_langchain_call() -> None:
    expected = ContractBasicInfo(
        contract_no="HT-2026-001",
        project_name="技术开发项目",
        seller={"name": "乙方公司"},
        buyer={"name": "甲方公司"},
    )

    with patch(
        "core.infrastructure.contracts.basic_info_extractor.invoke_structured",
        return_value=expected,
    ) as invoke:
        result = extract_contract_basic_info("合同正文")

    assert result == expected
    invoke.assert_called_once_with(
        BASIC_INFO_PROMPT,
        ContractBasicInfo,
        {"contract_text": "合同正文"},
    )
