from __future__ import annotations

import pytest

from core.contracts.normalize import normalize_date


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("2025年5月10日", "2025-05-10"),
        ("2025年05月10日", "2025-05-10"),
        ("2025年5月10号", "2025-05-10"),
        ("2025 年 5 月 10 日", "2025-05-10"),
        ("签订日期：2025年5月10日", "2025-05-10"),
        ("签订时间为2025年05月10日", "2025-05-10"),
        ("2025-5-10", "2025-05-10"),
        ("2025-05-10", "2025-05-10"),
        ("2025/5/10", "2025-05-10"),
        ("2025/05/10", "2025-05-10"),
        ("2025.5.10", "2025-05-10"),
        ("2025.05.10", "2025-05-10"),
        ("签订日期:2025-05-10", "2025-05-10"),
        ("Date: 2025/05/10", "2025-05-10"),
    ],
)
def test_normalize_date_full_date_cases(raw_value: str, expected: str) -> None:
    """完整日期应归一化为 YYYY-MM-DD。"""
    assert normalize_date(raw_value) == expected


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("2025年5月", "2025-05"),
        ("2025年05月", "2025-05"),
        ("2025 年 5 月", "2025-05"),
        ("签订时间：2025年5月", "2025-05"),
        ("2025-5", "2025-05"),
        ("2025-05", "2025-05"),
        ("2025/5", "2025-05"),
        ("2025/05", "2025-05"),
        ("2025.5", "2025-05"),
        ("2025.05", "2025-05"),
    ],
)
def test_normalize_date_year_month_cases(raw_value: str, expected: str) -> None:
    """只有年月的日期应归一化为 YYYY-MM。"""
    assert normalize_date(raw_value) == expected


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("2025年", "2025"),
        ("2025", "2025"),
        ("签订年份：2025年", "2025"),
    ],
)
def test_normalize_date_year_only_cases(raw_value: str, expected: str) -> None:
    """只有年份的日期应归一化为 YYYY。"""
    assert normalize_date(raw_value) == expected


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("2024-02-29", "2024-02-29"),
        ("2024年2月29日", "2024-02-29"),
        ("2025-12-31", "2025-12-31"),
        ("2025年1月1日", "2025-01-01"),
        ("2025-01-01", "2025-01-01"),
    ],
)
def test_normalize_date_boundary_valid_cases(raw_value: str, expected: str) -> None:
    """边界有效日期应被正确保留。"""
    assert normalize_date(raw_value) == expected


@pytest.mark.parametrize(
    "raw_value",
    [
        "",
        "   ",
        "\t\n",
        "待定",
        "签订日期待补充",
        "年月日",
        "2025年13月1日",
        "2025年0月1日",
        "2025年5月32日",
        "2025年5月0日",
        "2025-13-01",
        "2025-00-01",
        "2025-05-32",
        "2025-05-00",
        "2025/02/30",
        "2023-02-29",
        "2025年2月29日",
        "2025年5月10日至2029年5月9日",
        "自2025年5月10日起至2029年5月9日止",
        "2025年5月上旬",
        "2025年5月前",
        "05月10日",
        "5月10日",
    ],
)
def test_normalize_date_invalid_or_ambiguous_cases(raw_value: str) -> None:
    """非法、模糊或区间日期不应被归一化成单个有效日期。"""
    assert normalize_date(raw_value) == ""


def test_normalize_date_is_idempotent_for_normalized_full_date() -> None:
    """已经标准化的完整日期再次归一化后应保持不变。"""
    assert normalize_date("2025-05-10") == "2025-05-10"


def test_normalize_date_is_idempotent_for_normalized_year_month() -> None:
    """已经标准化的年月再次归一化后应保持不变。"""
    assert normalize_date("2025-05") == "2025-05"


def test_normalize_date_is_idempotent_for_normalized_year() -> None:
    """已经标准化的年份再次归一化后应保持不变。"""
    assert normalize_date("2025") == "2025"
