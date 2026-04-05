from __future__ import annotations

from fastapi import APIRouter

from core.application.contracts import check_basic_info
from core.domain.contracts.models import CheckBasicInfoRequest, CheckBasicInfoResponse

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


@router.post("/check-basic-info", response_model=CheckBasicInfoResponse)
def check_basic_info_api(payload: CheckBasicInfoRequest) -> CheckBasicInfoResponse:
    """接收合同文本和平台基础信息，返回基本信息核对结果。"""
    return check_basic_info(
        contract_text=payload.contract_text,
        platform_basic_info=payload.platform_basic_info,
    )
