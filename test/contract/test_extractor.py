from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.contracts.extractor as extractor_module
from core.contracts.models import ContractBasicInfo


def _build_fake_config() -> SimpleNamespace:
    return SimpleNamespace(
        ocr2json=SimpleNamespace(
            system_prompt="只返回 JSON",
            schema_json={
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
            },
        )
    )


def test_build_contract_basic_info_maps_structured_contract_basic_info_without_monkeypatch() -> None:
    """不依赖 monkeypatch 时，也应能把 structured.contract_basic_info 映射到模型。"""
    data = {
        "doc_id": "demo",
        "source": {},
        "processing": {},
        "raw_content": {},
        "structured": {
            "contract_basic_info": {
                "contract_no": "HT-2025-003",
                "project_name": "项目C",
                "sign_date": "2025年6月",
                "contract_period": "2025年6月1日至2029年5月31日",
                "transaction_amount": "30万元",
                "technology_transaction_amount": "30万元",
                "payment_mode": "一次性支付",
                "seller": {
                    "name": "中国科学技术大学",
                    "project_leader": "曹喆",
                    "legal_representative": "常进",
                    "legal_phone": "13515646364",
                    "address": "安徽省合肥市包河区金寨路96号",
                    "agent": "曹喆",
                    "agent_phone": "13515646364",
                },
                "buyer": {
                    "name": "深圳先进技术研究院",
                    "legal_representative": "刘陈立",
                    "legal_phone": "15818518712",
                    "address": "深圳市南山区西丽深圳大学城学苑大道1068号",
                    "agent": "胡战列",
                    "agent_phone": "15818518712",
                },
            }
        },
    }

    result = extractor_module._build_contract_basic_info(data)

    assert isinstance(result, ContractBasicInfo)
    assert result.model_dump() == data["structured"]["contract_basic_info"]


def test_extract_contract_basic_info_maps_structured_contract_basic_info(
    monkeypatch,
) -> None:
    """应从 structured.contract_basic_info 逐字段填充 ContractBasicInfo。"""
    data = {
        "doc_id": "demo",
        "source": {},
        "processing": {},
        "raw_content": {},
        "structured": {
            "contract_basic_info": {
                "contract_no": "HT-2025-001",
                "project_name": "小动物PET时间符合电子学研制",
                "sign_date": "2025年5月",
                "contract_period": "2025年5月10日至2029年5月9日",
                "transaction_amount": "人民币肆拾玖万元整",
                "technology_transaction_amount": "49万元",
                "payment_mode": "分期支付",
                "seller": {
                    "name": "中国科学技术大学",
                    "project_leader": "曹喆",
                    "legal_representative": "常进",
                    "legal_phone": "13515646364",
                    "address": "安徽省合肥市包河区金寨路96号",
                    "agent": "曹喆",
                    "agent_phone": "13515646364",
                },
                "buyer": {
                    "name": "深圳先进技术研究院",
                    "legal_representative": "刘陈立",
                    "legal_phone": "15818518712",
                    "address": "深圳市南山区西丽深圳大学城学苑大道1068号",
                    "agent": "胡战列",
                    "agent_phone": "15818518712",
                },
            }
        },
    }

    monkeypatch.setattr(
        extractor_module,
        "load_agent_config",
        lambda: _build_fake_config(),
    )
    monkeypatch.setattr(
        extractor_module,
        "run_message_and_get_reply",
        lambda user_message, work_description="": '{"mock": "reply"}',
    )
    monkeypatch.setattr(
        extractor_module,
        "parse_json_object",
        lambda reply_text: data,
    )

    result = extractor_module.extract_contract_basic_info("合同文本")

    assert isinstance(result, ContractBasicInfo)
    assert result.model_dump() == data["structured"]["contract_basic_info"]


def test_extract_contract_basic_info_calls_ai_chain_before_model_mapping(
    monkeypatch,
) -> None:
    """应先调用 AI，再解析 JSON，最后映射到 ContractBasicInfo。"""
    reply_text = '{"structured": {"contract_basic_info": {"contract_no": "HT-2025-002", "project_name": "", "sign_date": "", "contract_period": "", "transaction_amount": "", "technology_transaction_amount": "", "payment_mode": "", "seller": {"name": "", "project_leader": "", "legal_representative": "", "legal_phone": "", "address": "", "agent": "", "agent_phone": ""}, "buyer": {"name": "", "legal_representative": "", "legal_phone": "", "address": "", "agent": "", "agent_phone": ""}}}}'
    data = {
        "structured": {
            "contract_basic_info": {
                "contract_no": "HT-2025-002",
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
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        extractor_module,
        "load_agent_config",
        lambda: _build_fake_config(),
    )

    def fake_run_message_and_get_reply(user_message: str, work_description: str = "") -> str:
        calls.append(("run_message_and_get_reply", user_message))
        calls.append(("work_description", work_description))
        return reply_text

    def fake_parse_json_object(raw_reply_text: str) -> dict:
        calls.append(("parse_json_object", raw_reply_text))
        return data

    monkeypatch.setattr(
        extractor_module,
        "run_message_and_get_reply",
        fake_run_message_and_get_reply,
    )
    monkeypatch.setattr(
        extractor_module,
        "parse_json_object",
        fake_parse_json_object,
    )

    result = extractor_module.extract_contract_basic_info("合同正文")

    assert calls[0][0] == "run_message_and_get_reply"
    assert "合同文本" in calls[0][1]
    assert "合同正文" in calls[0][1]
    assert "目标 JSON 结构" in calls[0][1]
    assert calls[1] == ("work_description", "只返回 JSON")
    assert calls[2] == ("parse_json_object", reply_text)
    assert result.contract_no == "HT-2025-002"


def test_extract_contract_basic_info_live_ai_integration() -> None:
    """手动开启时，真实调用 AI 并走完整 extractor 链路。"""
    if os.getenv("RUN_LIVE_AI_TESTS") != "1":
        pytest.skip("set RUN_LIVE_AI_TESTS=1 to run live AI integration tests")

    contract_text = Path("test/output/contract_linearized.txt").read_text(encoding="utf-8")
    result = extractor_module.extract_contract_basic_info(contract_text)

    assert isinstance(result, ContractBasicInfo)
    assert isinstance(result.contract_no, str)
    assert isinstance(result.project_name, str)
    assert isinstance(result.sign_date, str)
    assert isinstance(result.seller.name, str)
    assert isinstance(result.buyer.name, str)
    assert any(
        [
            result.project_name,
            result.sign_date,
            result.seller.name,
            result.buyer.name,
        ]
    )
