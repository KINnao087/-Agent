from __future__ import annotations

import json

from core.domain.contracts.models import ContractBasicInfo
from core.infrastructure.ai import parse_json_object, run_message_and_get_reply
from core.infrastructure.ai.logger import get_logger
from core.infrastructure.ai.session import preview_text

logger = get_logger("contract-extractor")

BASIC_INFO_EXTRACTION_SYSTEM_PROMPT = """
你是科技合同基本信息提取助手。

你会收到一段合同正文文本。请只根据文本中明确出现的内容，提取科技合同基础信息，并严格输出单个合法 JSON 对象。

要求：
- 只能输出 JSON
- 不要输出解释
- 不要输出 Markdown
- 不允许臆造信息
- 金额、日期、电话、地址按原文提取
- 若合同中使用甲方/乙方、委托方/受托方等称谓，请结合上下文稳定映射为 buyer 和 seller
- 重点填写 structured.contract_basic_info，其余字段按目标结构保留
""".strip()

BASIC_INFO_EXTRACTION_SCHEMA: dict = {
    "structured": {
        "contract_basic_info": {
            "contract_no": "",
            "project_name": "",
            "sign_date": "",
            "contract_period": "",
            "transaction_amount": "",
            "technology_transaction_amount": "",
            "payment_mode": "",
            "seller": {
                "name": "",
                "project_leader": "",
                "legal_representative": "",
                "legal_phone": "",
                "address": "",
                "agent": "",
                "agent_phone": "",
            },
            "buyer": {
                "name": "",
                "legal_representative": "",
                "legal_phone": "",
                "address": "",
                "agent": "",
                "agent_phone": "",
            },
        }
    }
}


def _build_contract_basic_info(data: dict) -> ContractBasicInfo:
    """从 schema 风格结果中构造 ContractBasicInfo。"""
    basic_info = data["structured"]["contract_basic_info"]

    return ContractBasicInfo(
        contract_no=basic_info["contract_no"],
        project_name=basic_info["project_name"],
        sign_date=basic_info["sign_date"],
        contract_period=basic_info["contract_period"],
        transaction_amount=basic_info["transaction_amount"],
        technology_transaction_amount=basic_info["technology_transaction_amount"],
        payment_mode=basic_info["payment_mode"],
        seller={
            "name": basic_info["seller"]["name"],
            "project_leader": basic_info["seller"]["project_leader"],
            "legal_representative": basic_info["seller"]["legal_representative"],
            "legal_phone": basic_info["seller"]["legal_phone"],
            "address": basic_info["seller"]["address"],
            "agent": basic_info["seller"]["agent"],
            "agent_phone": basic_info["seller"]["agent_phone"],
        },
        buyer={
            "name": basic_info["buyer"]["name"],
            "legal_representative": basic_info["buyer"]["legal_representative"],
            "legal_phone": basic_info["buyer"]["legal_phone"],
            "address": basic_info["buyer"]["address"],
            "agent": basic_info["buyer"]["agent"],
            "agent_phone": basic_info["buyer"]["agent_phone"],
        },
    )


def _build_extract_user_message(contract_text: str) -> str:
    """构造合同基本信息提取提示词。"""
    schema_json_text = json.dumps(BASIC_INFO_EXTRACTION_SCHEMA, ensure_ascii=False, indent=2)
    return (
        "请根据以下合同文本提取信息，并严格输出为指定 JSON 结构。\n"
        "只返回单个合法 JSON 对象，不要输出解释，不要输出 Markdown。\n"
        "请重点填写 structured.contract_basic_info，其他字段按目标结构保留。\n\n"
        f"目标 JSON 结构：\n{schema_json_text}\n\n"
        f"合同文本：\n{contract_text}"
    )


def extract_contract_basic_info(contract_text: str) -> ContractBasicInfo:
    """从合同文本中提取 contract_basic_info。"""
    user_message = _build_extract_user_message(contract_text)

    logger.info("已根据内置提示词构造基本信息提取请求")
    reply_text = run_message_and_get_reply(
        user_message=user_message,
        work_description=BASIC_INFO_EXTRACTION_SYSTEM_PROMPT,
    )
    logger.info("AI 原始返回预览：\n{}", preview_text(reply_text))
    data = parse_json_object(reply_text)
    return _build_contract_basic_info(data)
