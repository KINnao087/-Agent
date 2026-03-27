from __future__ import annotations

import pytest

from core.contracts.normalize import normalize_period


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("2025年5月10日至2029年5月9日", "2025-05-10~2029-05-09"),
        ("自2025年5月10日起至2029年5月9日止", "2025-05-10~2029-05-09"),
        ("合同周期：2025年05月10日至2029年05月09日", "2025-05-10~2029-05-09"),
        ("2025-5-10至2029-5-9", "2025-05-10~2029-05-09"),
        ("2025/05/10到2029/05/09", "2025-05-10~2029-05-09"),
        ("2025.05.10 ~ 2029.05.09", "2025-05-10~2029-05-09"),
        ("2025-05-10-2029-05-09", "2025-05-10~2029-05-09"),
        ("2025年5月至2029年4月", "2025-05~2029-04"),
        ("合同期限：2025-05至2029-04", "2025-05~2029-04"),
        ("2025年至2029年", "2025~2029"),
        ("2025~2029", "2025~2029"),
        ("2025-05-10~2029-05-09", "2025-05-10~2029-05-09"),
    ],
)
def test_normalize_period_valid_cases(raw_value: str, expected: str) -> None:
    """明确的合同起止区间应归一化为 start~end。"""
    assert normalize_period(raw_value) == expected


@pytest.mark.parametrize(
    "raw_value",
    [
        "",
        "   ",
        "\t\n",
        "待定",
        "合同周期待补充",
        "2025年5月10日",
        "2025-05",
        "2025",
        "2025年5月10日，2029年5月9日",
        "签订日期2025年5月10日，验收日期2029年5月9日",
        "2025年5月10日至2029年5月9日至2030年5月9日",
        "2025年13月10日至2029年5月9日",
        "2025年5月10日至2029年13月9日",
        "2025-02-30至2029-05-09",
        "2025年5月上旬至2029年4月",
        "2025年5月前至2029年4月",
        "05月10日至2029年5月9日",
        "2025年5月10日至05月09日",
    ],
)
def test_normalize_period_invalid_or_ambiguous_cases(raw_value: str) -> None:
    """非明确区间、模糊区间或非法区间不应被归一化。"""
    assert normalize_period(raw_value) == ""


def test_normalize_period_is_idempotent_for_normalized_full_date_range() -> None:
    """已经标准化的完整日期区间再次归一化后应保持不变。"""
    assert normalize_period("2025-05-10~2029-05-09") == "2025-05-10~2029-05-09"


def test_normalize_period_is_idempotent_for_normalized_year_month_range() -> None:
    """已经标准化的年月区间再次归一化后应保持不变。"""
    assert normalize_period("2025-05~2029-04") == "2025-05~2029-04"


def test_normalize_period_is_idempotent_for_normalized_year_range() -> None:
    """已经标准化的年份区间再次归一化后应保持不变。"""
    assert normalize_period("2025~2029") == "2025~2029"
