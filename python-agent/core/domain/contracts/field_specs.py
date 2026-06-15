from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


FieldKind = Literal["text", "phone", "amount", "date", "period"]


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """定义一个参与核对的字段。"""

    path: str
    label: str
    kind: FieldKind


FIELD_SPECS: tuple[FieldSpec, ...] = (
    FieldSpec("contract_no", "合同编号", "text"),
    FieldSpec("project_name", "项目名称", "text"),
    FieldSpec("sign_date", "签订日期", "date"),
    FieldSpec("contract_period", "核对合同周期", "period"),
    FieldSpec("transaction_amount", "成交金额", "amount"),
    FieldSpec("technology_transaction_amount", "技术交易金额", "amount"),
    FieldSpec("payment_mode", "支付方式", "text"),
    FieldSpec("seller.name", "卖方名称", "text"),
    FieldSpec("seller.project_leader", "项目负责人（卖方）", "text"),
    FieldSpec("seller.legal_representative", "卖方法人代表", "text"),
    FieldSpec("seller.legal_phone", "卖方法人电话", "phone"),
    FieldSpec("seller.address", "卖方联系地址", "text"),
    FieldSpec("seller.agent", "卖方经办人", "text"),
    FieldSpec("seller.agent_phone", "卖方经办人电话", "phone"),
    FieldSpec("buyer.name", "买方名称", "text"),
    FieldSpec("buyer.legal_representative", "买方法人代表", "text"),
    FieldSpec("buyer.legal_phone", "买方法人电话", "phone"),
    FieldSpec("buyer.address", "买方联系地址", "text"),
    FieldSpec("buyer.agent", "买方经办人", "text"),
    FieldSpec("buyer.agent_phone", "买方经办人电话", "phone"),
)

