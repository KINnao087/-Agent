from __future__ import annotations

from core.domain.contracts.compare import build_summary, compare_basic_info
from core.domain.contracts.models import (
    CheckBasicInfoResponse,
    ContractBasicInfo,
)
from core.infrastructure.contracts import extract_contract_basic_info


def check_basic_info(
    contract_text: str,
    platform_basic_info: ContractBasicInfo,
) -> CheckBasicInfoResponse:
    contract_basic_info = extract_contract_basic_info(contract_text)
    compare_result, flat_result = compare_basic_info(
        contract_basic_info,
        platform_basic_info,
    )
    return CheckBasicInfoResponse(
        contract_basic_info=contract_basic_info,
        compare_result=compare_result,
        summary=build_summary(flat_result),
    )


check_basic_info_service = check_basic_info
