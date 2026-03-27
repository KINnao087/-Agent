from __future__ import annotations

from fastapi import APIRouter

from core.contracts.models import CheckBasicInfoRequest, CheckBasicInfoResponse
from core.contracts.service import check_basic_info_service

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


@router.post("/check-basic-info", response_model=CheckBasicInfoResponse)
def check_basic_info_api(payload: CheckBasicInfoRequest) -> CheckBasicInfoResponse:
    """HTTP 接口入口：接收合同文本和平台基本信息，返回核对结果。"""
    return check_basic_info_service(
        contract_text=payload.contract_text,
        platform_basic_info=payload.platform_basic_info,
    )
