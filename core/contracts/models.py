from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


CompareStatus = Literal[
    "match",
    "mismatch",
    "missing_in_contract",
    "missing_in_platform",
    "both_empty",
]


class SellerBasicInfo(BaseModel):
    """卖方基础信息。"""

    name: str = ""
    project_leader: str = ""
    legal_representative: str = ""
    legal_phone: str = ""
    address: str = ""
    agent: str = ""
    agent_phone: str = ""


class BuyerBasicInfo(BaseModel):
    """买方基础信息。"""

    name: str = ""
    legal_representative: str = ""
    legal_phone: str = ""
    address: str = ""
    agent: str = ""
    agent_phone: str = ""


class ContractBasicInfo(BaseModel):
    """科技合同基本信息。字段结构保持当前已确定设计。"""

    contract_no: str = ""
    project_name: str = ""
    sign_date: str = ""
    contract_period: str = ""
    transaction_amount: str = ""
    technology_transaction_amount: str = ""
    payment_mode: str = ""
    seller: SellerBasicInfo = Field(default_factory=SellerBasicInfo)
    buyer: BuyerBasicInfo = Field(default_factory=BuyerBasicInfo)


class CompareFieldResult(BaseModel):
    """单个字段的核对结果。"""

    label: str = ""
    contract_value: str = ""
    platform_value: str = ""
    normalized_contract_value: str = ""
    normalized_platform_value: str = ""
    status: CompareStatus = "both_empty"


class SellerCompareResult(BaseModel):
    """卖方各字段的 compare_result 结构。"""

    name: CompareFieldResult = Field(default_factory=CompareFieldResult)
    project_leader: CompareFieldResult = Field(default_factory=CompareFieldResult)
    legal_representative: CompareFieldResult = Field(default_factory=CompareFieldResult)
    legal_phone: CompareFieldResult = Field(default_factory=CompareFieldResult)
    address: CompareFieldResult = Field(default_factory=CompareFieldResult)
    agent: CompareFieldResult = Field(default_factory=CompareFieldResult)
    agent_phone: CompareFieldResult = Field(default_factory=CompareFieldResult)


class BuyerCompareResult(BaseModel):
    """买方各字段的 compare_result 结构。"""

    name: CompareFieldResult = Field(default_factory=CompareFieldResult)
    legal_representative: CompareFieldResult = Field(default_factory=CompareFieldResult)
    legal_phone: CompareFieldResult = Field(default_factory=CompareFieldResult)
    address: CompareFieldResult = Field(default_factory=CompareFieldResult)
    agent: CompareFieldResult = Field(default_factory=CompareFieldResult)
    agent_phone: CompareFieldResult = Field(default_factory=CompareFieldResult)


class ContractBasicInfoCompareResult(BaseModel):
    """整体 compare_result。结构与 contract_basic_info 基本对应。"""

    contract_no: CompareFieldResult = Field(default_factory=CompareFieldResult)
    project_name: CompareFieldResult = Field(default_factory=CompareFieldResult)
    sign_date: CompareFieldResult = Field(default_factory=CompareFieldResult)
    contract_period: CompareFieldResult = Field(default_factory=CompareFieldResult)
    transaction_amount: CompareFieldResult = Field(default_factory=CompareFieldResult)
    technology_transaction_amount: CompareFieldResult = Field(default_factory=CompareFieldResult)
    payment_mode: CompareFieldResult = Field(default_factory=CompareFieldResult)
    seller: SellerCompareResult = Field(default_factory=SellerCompareResult)
    buyer: BuyerCompareResult = Field(default_factory=BuyerCompareResult)


class Summary(BaseModel):
    """核对摘要统计。"""

    total_fields: int = 0
    compared_fields: int = 0
    matched_fields: int = 0
    mismatched_fields: int = 0
    missing_in_contract_fields: int = 0
    missing_in_platform_fields: int = 0
    both_empty_fields: int = 0
    match_rate: float = 0.0
    mismatch_paths: list[str] = Field(default_factory=list)


class CheckBasicInfoRequest(BaseModel):
    """POST /api/contracts/check-basic-info 的请求体。"""

    contract_text: str
    platform_basic_info: ContractBasicInfo


class CheckBasicInfoResponse(BaseModel):
    """POST /api/contracts/check-basic-info 的响应体。"""

    contract_basic_info: ContractBasicInfo
    compare_result: ContractBasicInfoCompareResult
    summary: Summary

