from __future__ import annotations

from core.domain.contracts.models import ContractBasicInfo
from core.infrastructure.ai import AIConfigRole, invoke_structured
from core.infrastructure.ai.prompts import BASIC_INFO_PROMPT


def extract_contract_basic_info(contract_text: str) -> ContractBasicInfo:
    return invoke_structured(
        BASIC_INFO_PROMPT,
        ContractBasicInfo,
        {"contract_text": contract_text},
        role=AIConfigRole.TEXT,
    )
