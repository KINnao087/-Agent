from __future__ import annotations

import core.contracts.compare as compare_module
from core.contracts.field_specs import FieldSpec
from core.contracts.models import (
    CompareFieldResult,
    ContractBasicInfo,
    Summary,
)


def test_build_compare_field_result_returns_expected_model() -> None:
    """单字段比较结果应被封装为 CompareFieldResult。"""
    result = compare_module.build_compare_field_result(
        label="签订日期",
        contract_value="2025年5月10日",
        platform_value="2025-05-10",
        normalized_contract_value="2025-05-10",
        normalized_platform_value="2025-05-10",
        status="match",
    )

    assert isinstance(result, CompareFieldResult)
    assert result.model_dump() == {
        "label": "签订日期",
        "contract_value": "2025年5月10日",
        "platform_value": "2025-05-10",
        "normalized_contract_value": "2025-05-10",
        "normalized_platform_value": "2025-05-10",
        "status": "match",
    }


def test_compare_basic_info_returns_compare_result_and_flat_results(monkeypatch) -> None:
    """整体比较应返回嵌套 compare_result 和平铺 flat_results。"""
    monkeypatch.setattr(
        compare_module,
        "FIELD_SPECS",
        (
            FieldSpec("contract_no", "合同编号", "text"),
            FieldSpec("sign_date", "签订日期", "date"),
            FieldSpec("seller.agent_phone", "卖方经办人电话", "phone"),
            FieldSpec("project_name", "项目名称", "text"),
            FieldSpec("buyer.agent", "买方经办人", "text"),
            FieldSpec("buyer.address", "买方联系地址", "text"),
            FieldSpec("technology_transaction_amount", "技术交易金额", "amount"),
        ),
    )

    contract_basic_info = ContractBasicInfo(
        contract_no="HT-2025-001",
        project_name="项目A",
        sign_date="2025年5月10日",
        seller={
            "agent_phone": "136 0000 0000",
        },
        buyer={
            "address": "深圳市南山区西丽深圳大学城学苑大道1068号",
        },
    )
    platform_basic_info = ContractBasicInfo(
        contract_no="HT-2025-001",
        project_name="项目B",
        sign_date="2025-05-10",
        seller={
            "agent_phone": "13600000000",
        },
        buyer={
            "agent": "李四",
        },
    )

    compare_result, flat_results = compare_module.compare_basic_info(
        contract_basic_info=contract_basic_info,
        platform_basic_info=platform_basic_info,
    )

    compare_result_dict = (
        compare_result.model_dump()
        if hasattr(compare_result, "model_dump")
        else compare_result
    )
    flat_result_map = {item["path"]: item for item in flat_results}

    assert flat_result_map["contract_no"]["status"] == "match"
    assert flat_result_map["sign_date"]["status"] == "match"
    assert flat_result_map["sign_date"]["normalized_contract_value"] == "2025-05-10"
    assert flat_result_map["sign_date"]["normalized_platform_value"] == "2025-05-10"
    assert flat_result_map["seller.agent_phone"]["status"] == "match"
    assert flat_result_map["seller.agent_phone"]["normalized_contract_value"] == "13600000000"
    assert flat_result_map["seller.agent_phone"]["normalized_platform_value"] == "13600000000"
    assert flat_result_map["project_name"]["status"] == "mismatch"
    assert flat_result_map["buyer.agent"]["status"] == "missing_in_contract"
    assert flat_result_map["buyer.address"]["status"] == "missing_in_platform"
    assert flat_result_map["technology_transaction_amount"]["status"] == "both_empty"

    assert compare_result_dict["contract_no"]["status"] == "match"
    assert compare_result_dict["sign_date"]["status"] == "match"
    assert compare_result_dict["seller"]["agent_phone"]["status"] == "match"
    assert compare_result_dict["project_name"]["status"] == "mismatch"
    assert compare_result_dict["buyer"]["agent"]["status"] == "missing_in_contract"
    assert compare_result_dict["buyer"]["address"]["status"] == "missing_in_platform"
    assert (
        compare_result_dict["technology_transaction_amount"]["status"] == "both_empty"
    )
    assert len(flat_results) == 7


def test_build_summary_counts_statuses_and_match_rate() -> None:
    """summary 应正确统计各状态数量和匹配率。"""
    flat_results = [
        {"path": "contract_no", "status": "match"},
        {"path": "sign_date", "status": "match"},
        {"path": "seller.agent_phone", "status": "match"},
        {"path": "project_name", "status": "mismatch"},
        {"path": "buyer.agent", "status": "missing_in_contract"},
        {"path": "buyer.address", "status": "missing_in_platform"},
        {"path": "technology_transaction_amount", "status": "both_empty"},
    ]

    summary = compare_module.build_summary(flat_results)

    assert isinstance(summary, Summary)
    assert summary.model_dump() == {
        "total_fields": 7,
        "compared_fields": 6,
        "matched_fields": 3,
        "mismatched_fields": 1,
        "missing_in_contract_fields": 1,
        "missing_in_platform_fields": 1,
        "both_empty_fields": 1,
        "match_rate": 0.5,
        "mismatch_paths": ["project_name"],
    }


def test_build_summary_returns_zero_summary_for_empty_results() -> None:
    """空结果列表应返回全 0 的 summary。"""
    summary = compare_module.build_summary([])

    assert isinstance(summary, Summary)
    assert summary.model_dump() == {
        "total_fields": 0,
        "compared_fields": 0,
        "matched_fields": 0,
        "mismatched_fields": 0,
        "missing_in_contract_fields": 0,
        "missing_in_platform_fields": 0,
        "both_empty_fields": 0,
        "match_rate": 0.0,
        "mismatch_paths": [],
    }
