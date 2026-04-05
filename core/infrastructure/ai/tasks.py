from __future__ import annotations

import base64
import json
from dataclasses import replace
from pathlib import Path

from .config import AgentConfig, load_agent_config
from .json_parser import parse_json_object
from .logger import get_logger
from .llm_client import build_provider
from .session import AgentRunner

logger = get_logger("ai-tasks")

OCR2JSON_SYSTEM_PROMPT = """
你是一个科技合同文档解析助手。你会收到一个 OCR 输入对象，其中通常包含 contract、attachments、invoice 三个列表。
contract 是主合同页 OCR JSON 列表，attachments 是附件页 OCR JSON 列表，invoice 是发票或收据页 OCR JSON 列表。

请综合这些信息，严格输出为合法 JSON，并尽量提取完整、准确、可追溯的结构化结果。

要求：
- 只能输出 JSON
- 不要输出解释
- 不要输出 Markdown
- 所有字段必须保留
- 文本字段缺失填 ""
- 数组字段缺失填 []
- 无法判断的布尔字段填 null
- 不允许臆造信息
- 金额、日期、电话、账号按原文提取
- 如果同一信息在主合同、附件、发票中出现冲突，优先采用主合同正文；附件和发票仅用于补充或佐证
- structured.extra.attachments_declared_in_contract 需要结合附件 OCR 内容写出每个附件的关键信息摘要；如果附件没有明确标题，可以使用“附件1”“附件2”等稳定名称
- sections 可以按合同正文和附件内容补充重要条款或段落标题
- structured.contract_basic_info 需要按字段定义提取科技合同基本信息；如果合同中使用甲方/乙方、委托方/受托方等称谓，请结合上下文稳定映射到买方和卖方
- 如果附件或发票没有提供有效信息，对应相关字段保持空值或空数组
""".strip()

OCR2JSON_USER_PROMPT_TEMPLATE = """
请根据以下 OCR 输入提取信息，并输出为指定 JSON 结构。

文件名：{{file_name}}

目标 JSON 结构：
{{schema_json}}

输入说明：
- contract：主合同 OCR JSON 列表
- attachments：附件 OCR JSON 列表
- invoice：发票/收据 OCR JSON 列表
- ocr_json：完整 OCR 输入对象

主合同 OCR JSON 列表：
{{contract}}

附件 OCR JSON 列表：
{{attachments}}

发票 OCR JSON 列表：
{{invoice}}

完整 OCR 输入对象：
{{ocr_json}}

提取要求补充：
1. 先从 contract 中提取合同主体信息。
2. 再结合 attachments 补充项目名称、交付内容、技术指标、验收要求、知识产权、附表清单等信息。
3. 如果 attachments 中存在可总结的附件内容，请将每个附件的重要内容整理进 structured.extra.attachments_declared_in_contract 数组。
4. 如果 invoice 中存在有效金额、开票信息或收款相关信息，只能作为补充参考，不能覆盖合同正文中明确写出的值。
5. 需要完整填写 structured.contract_basic_info。该对象用于提取科技合同基本信息，包含 contract_no（合同编号）、project_name（项目名称）、sign_date（签订日期）、contract_period（合同周期原文）、transaction_amount（成交金额）、technology_transaction_amount（技术交易金额）、payment_mode（支付方式），以及 seller 和 buyer 两个主体对象。
6. seller 表示卖方，包含 name（名称）、project_leader（项目负责人）、legal_representative（法人代表）、legal_phone（法人电话）、address（联系地址）、agent（经办人）、agent_phone（经办人电话）；buyer 表示买方，包含 name、legal_representative、legal_phone、address、agent、agent_phone。
7. 若合同正文使用甲方/乙方、委托方/受托方等称谓，请结合合同语义映射为买方和卖方；在技术开发（委托）合同中通常委托方/甲方为买方，受托方/乙方为卖方，但如果合同正文明确写明买卖方向，则以正文明确表述为准。
8. 金额、日期、电话必须按原文提取，不要自行换算、补全或标准化；无法确认时填空字符串。
9. 最终必须返回单个 JSON 对象。
""".strip()

OCR2JSON_SCHEMA_JSON: dict = {
    "doc_id": "",
    "source": {
        "file_name": "",
        "file_type": "",
        "input_type": "",
        "page_count": 0,
        "language": "zh-CN",
    },
    "processing": {
        "ocr_used": False,
        "pdf_text_used": False,
        "preferred_text_source": "",
        "status": "success",
        "warnings": [],
    },
    "raw_content": {
        "title": "",
        "full_text_available": True,
    },
    "structured": {
        "doc_type": "contract",
        "doc_subtype": "",
        "common_fields": {
            "title": "",
            "document_no": "",
            "sign_date": "",
            "sign_location": "",
            "effective_period": "",
            "party_a": "",
            "party_b": "",
            "amount": "",
        },
        "typed_fields": {
            "project_name": "",
            "cooperation_mode": "",
            "contract_period": {
                "raw_text": "",
                "start_date": "",
                "end_date": "",
                "research_phase": {
                    "start_date": "",
                    "end_date": "",
                },
                "warranty_consulting_phase": {
                    "start_date": "",
                    "end_date": "",
                },
            },
            "payment": {
                "total_amount": "",
                "payment_mode": "",
                "stages": [],
            },
            "party_a_info": {
                "name": "",
                "address": "",
                "legal_representative": "",
                "project_contact": "",
                "contact_phone": "",
                "email": "",
            },
            "party_b_info": {
                "name": "",
                "address": "",
                "legal_representative": "",
                "project_contact": "",
                "contact_phone": "",
                "email": "",
            },
            "bank_info": {
                "account_name": "",
                "bank_name": "",
                "bank_account": "",
            },
            "deliverables": [],
            "delivery": {
                "deadline": "",
                "location": "",
            },
            "acceptance": {
                "rule": "",
            },
            "intellectual_property": {
                "patent_application_right": "",
                "ownership_summary": [],
            },
            "dispute_resolution": "",
            "effectiveness": "",
        },
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
        },
        "entities": [],
        "sections": [],
        "extra": {
            "seal_info": {
                "party_a_seal_present": None,
                "party_b_seal_present": None,
                "cross_page_seal_present": None,
            },
            "attachments_declared_in_contract": [],
            "contract_copies": "",
        },
    },
}


def _merge_system_prompts(base_system: str, work_description: str) -> str:
    """合并基础 system 提示词和当前工作描述。"""
    parts: list[str] = []
    if base_system.strip():
        parts.append(base_system.strip())
    if work_description.strip():
        parts.append(work_description.strip())
    return "\n\n".join(parts)


def _run_message_with_config(
    config: AgentConfig,
    user_message: str,
    work_description: str = "",
    max_steps: int = 1,
    enable_thinking_stream: bool = False,
) -> str:
    """使用给定配置发送单轮消息，并返回 AI 最终回复。"""
    runtime_config = replace(
        config,
        base_system=_merge_system_prompts(config.base_system, work_description),
        tool_defs=[],
    )
    logger.info("AI system prompt:\n{}", runtime_config.base_system)
    logger.info("AI user message:\n{}", user_message)
    runner = AgentRunner(runtime_config)
    reply, _ = runner.run_and_get_reply(
        task=user_message,
        max_steps=max_steps,
        enable_thinking_stream=enable_thinking_stream,
    )
    return reply


def run_message_and_get_reply(
    user_message: str,
    work_description: str = "",
    config_path: str | Path | None = None,
    max_steps: int = 1,
    enable_thinking_stream: bool = False,
) -> str:
    """对外提供单轮 AI 调用接口，由 AI 包内部完成 system 提示词组装。"""
    config = load_agent_config(config_path)
    return _run_message_with_config(
        config=config,
        user_message=user_message,
        work_description=work_description,
        max_steps=max_steps,
        enable_thinking_stream=enable_thinking_stream,
    )


def _img2b64_dataurl(image_path: str | Path) -> str:
    """把本地图片转换成base64格式"""
    path = Path(image_path)
    image_bytes = path.read_bytes()
    image_base64 = base64.b64encode(image_bytes).decode("ascii")

    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        mime_type = "image/jpeg"
    elif suffix == ".webp":
        mime_type = "image/webp"
    else:
        mime_type = "image/png"

    return f"data:{mime_type};base64,{image_base64}"


def run_image_and_get_reply(
    image_path: str | Path,
    user_message: str,
    work_description: str = "",
    config_path: str | Path | None = None,
) -> str:
    """发送一张本地图片和一段文本给多模态模型，并返回回复文本。"""
    config = load_agent_config(config_path)
    provider = build_provider(config)
    runtime_system = _merge_system_prompts(config.base_system, work_description)
    data_url = _img2b64_dataurl(image_path)

    messages = [
        {"role": "system", "content": runtime_system},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_message},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]

    logger.info("AI system prompt:\n{}", runtime_system)
    logger.info("AI user message:\n{}", user_message)
    logger.info("AI image path: {}", Path(image_path))

    result = provider.chat(
        model=config.model,
        tool_defs=[],
        messages=messages,
    )
    return result.content


def _build_ocr2json_user_message(ocr_payload: dict) -> str:
    """根据 OCR 输入对象和内置模板构造发给模型的用户消息。"""
    file_name = Path(str(ocr_payload.get("input_path", ""))).name
    ocr_json_text = json.dumps(ocr_payload, ensure_ascii=False, indent=2)
    contract_json_text = json.dumps(ocr_payload.get("contract", []), ensure_ascii=False, indent=2)
    attachments_json_text = json.dumps(
        ocr_payload.get("attachments", []), ensure_ascii=False, indent=2
    )
    invoice_json_text = json.dumps(ocr_payload.get("invoice", []), ensure_ascii=False, indent=2)
    schema_json_text = json.dumps(OCR2JSON_SCHEMA_JSON, ensure_ascii=False, indent=2)

    return (
        OCR2JSON_USER_PROMPT_TEMPLATE
        .replace("{{file_name}}", file_name)
        .replace("{{ocr_json}}", ocr_json_text)
        .replace("{{contract}}", contract_json_text)
        .replace("{{attachments}}", attachments_json_text)
        .replace("{{attachment}}", attachments_json_text)
        .replace("{{invoice}}", invoice_json_text)
        .replace("{{schema_json}}", schema_json_text)
        .replace("{{input_text}}", ocr_json_text)
    )


def structure_ocr_json(
    ocr_payload: dict,
    config_path: str | Path | None = None,
    max_steps: int = 1,
    enable_thinking_stream: bool = False,
) -> dict:
    """把 OCR 输入对象发送给 AI，并返回解析后的结构化 JSON 对象。"""
    config = load_agent_config(config_path)
    reply_text = _run_message_with_config(
        config=config,
        user_message=_build_ocr2json_user_message(ocr_payload),
        work_description=OCR2JSON_SYSTEM_PROMPT,
        max_steps=max_steps,
        enable_thinking_stream=enable_thinking_stream,
    )
    return parse_json_object(reply_text)
