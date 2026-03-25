from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from .config import AgentConfig, load_agent_config
from .json_parser import parse_json_object
from .session import AgentRunner


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


def _build_ocr2json_user_message(config: AgentConfig, ocr_payload: dict) -> str:
    """根据 OCR 输入对象和配置模板构造发给模型的用户消息。"""
    user_template = config.ocr2json.user_prompt_template.strip()
    if not user_template:
        raise ValueError("config field 'ocr2json.user_prompt_template' is required")

    file_name = Path(str(ocr_payload.get("input_path", ""))).name
    ocr_json_text = json.dumps(ocr_payload, ensure_ascii=False, indent=2)
    contract_json_text = json.dumps(ocr_payload.get("contract", []), ensure_ascii=False, indent=2)
    attachments_json_text = json.dumps(
        ocr_payload.get("attachments", []), ensure_ascii=False, indent=2
    )
    invoice_json_text = json.dumps(ocr_payload.get("invoice", []), ensure_ascii=False, indent=2)
    schema_json_text = json.dumps(config.ocr2json.schema_json, ensure_ascii=False, indent=2)

    return (
        user_template
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
    work_description = config.ocr2json.system_prompt.strip()
    if not work_description:
        raise ValueError("config field 'ocr2json.system_prompt' is required")

    user_message = _build_ocr2json_user_message(config, ocr_payload)
    reply_text = _run_message_with_config(
        config=config,
        user_message=user_message,
        work_description=work_description,
        max_steps=max_steps,
        enable_thinking_stream=enable_thinking_stream,
    )
    return parse_json_object(reply_text)
