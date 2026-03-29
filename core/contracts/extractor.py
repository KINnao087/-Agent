from __future__ import annotations

import json

from core.ai import load_agent_config, parse_json_object, run_message_and_get_reply
from core.ai.logger import get_logger
from core.contracts.models import ContractBasicInfo

logger = get_logger("contract-extractor")


def _build_contract_basic_info(data: dict) -> ContractBasicInfo:
    """从 schema_json 风格结果中构造 ContractBasicInfo。"""
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


def _build_extract_user_message(contract_text: str, schema_json: dict) -> str:
    """构造合同基本信息提取提示词。"""
    schema_json_text = json.dumps(schema_json, ensure_ascii=False, indent=2)
    return (
        "请根据以下合同文本提取信息，并严格输出为指定 JSON 结构。\n"
        "只返回单个合法 JSON 对象，不要输出解释，不要输出 Markdown。\n"
        "请重点填写 structured.contract_basic_info，其他字段按目标结构保留。\n\n"
        f"目标 JSON 结构：\n{schema_json_text}\n\n"
        f"合同文本：\n{contract_text}"
    )


def extract_contract_basic_info(contract_text: str) -> ContractBasicInfo:
    """从合同文本中提取 contract_basic_info。"""
    config = load_agent_config()
    work_description = config.ocr2json.system_prompt.strip()
    user_message = _build_extract_user_message(contract_text, config.ocr2json.schema_json)

    logger.info("Build extractor prompt from config.ocr2json")
    reply_text = run_message_and_get_reply(
        user_message=user_message,
        work_description=work_description,
    )
    logger.info("AI raw reply:\n{}", reply_text)
    data = parse_json_object(reply_text)
    return _build_contract_basic_info(data)
