from __future__ import annotations

from core.contracts.compare import build_summary, compare_basic_info
from core.contracts.extractor import extract_contract_basic_info
from core.contracts.models import (
    CheckBasicInfoResponse,
    ContractBasicInfo,
)


def check_basic_info_service(
    contract_text: str,
    platform_basic_info: ContractBasicInfo,
) -> CheckBasicInfoResponse:
    """服务入口：编排“提取 -> 核对 -> 汇总”三个步骤。"""
    raise NotImplementedError("TODO: orchestrate basic info checking flow")

