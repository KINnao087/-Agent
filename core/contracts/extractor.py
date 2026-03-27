from __future__ import annotations

from core.contracts.models import ContractBasicInfo


def build_extract_prompt(contract_text: str) -> str:
    """构造合同基本信息提取提示词。"""
    raise NotImplementedError("TODO: build prompt for basic info extraction")


def extract_contract_basic_info(contract_text: str) -> ContractBasicInfo:
    """从合同文本中提取 contract_basic_info。"""
    raise NotImplementedError("TODO: extract contract_basic_info from contract_text")

