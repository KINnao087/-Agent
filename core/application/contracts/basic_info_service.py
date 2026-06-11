from __future__ import annotations

from core.application.workflows.basic_info import BASIC_INFO_GRAPH
from core.domain.contracts.models import (
    CheckBasicInfoResponse,
    ContractBasicInfo,
)


def check_basic_info(
    contract_text: str,
    platform_basic_info: ContractBasicInfo,
) -> CheckBasicInfoResponse:
    state = BASIC_INFO_GRAPH.invoke(
        {
            "contract_text": contract_text,
            "platform_basic_info": platform_basic_info,
        }
    )
    return state["response"]


check_basic_info_service = check_basic_info
