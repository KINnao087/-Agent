from __future__ import annotations

from core.domain.contracts.compare import build_summary, compare_basic_info
from core.domain.contracts.models import (
    CheckBasicInfoResponse,
    ContractBasicInfo,
)
from core.infrastructure.contracts.basic_info_extractor import extract_contract_basic_info


def check_basic_info(
    contract_text: str,
    platform_basic_info: ContractBasicInfo,
) -> CheckBasicInfoResponse:
    """服务入口：编排“提取 -> 核对 -> 汇总”三个步骤。"""
    contract_basic_info = extract_contract_basic_info(contract_text)
    compare_res, flat_res = compare_basic_info(contract_basic_info, platform_basic_info)
    summary = build_summary(flat_res)

    return CheckBasicInfoResponse(
        contract_basic_info=contract_basic_info,
        compare_result=compare_res,
        summary=summary,
    )


check_basic_info_service = check_basic_info
