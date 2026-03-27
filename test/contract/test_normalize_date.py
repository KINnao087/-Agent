from __future__ import annotations

import pytest

from core.contracts.normalize import _normalize_date_ch


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("2025年5月10日", "2025-05-10"),
        ("2025年05月10日", "2025-05-10"),
        ("2025年5月10号", "2025-05-10"),
        ("签订时间：2025年5月10日", "2025-05-10"),
        ("2025 年 5 月 10 日", "2025-05-10"),
        ("2025年5月", "2025-05"),
        ("签订时间：2025年05月", "2025-05"),
        ("2025年", "2025"),
    ],
)
def test_normalize_date_ch_valid_cases(raw_value: str, expected: str) -> None:
    """中文单日期应被正确提取并归一化。"""
    assert _normalize_date_ch(raw_value) == expected


@pytest.mark.parametrize(
    "raw_value",
    [
        "",
        "2025-05-10",
        "签订日期待定",
        "2025年13月1日",
        "2025年5月32日",
        "2025年5月10日至2029年5月9日",
        "自2025年5月10日起至2029年5月9日止",
    ],
)
def test_normalize_date_ch_invalid_or_ambiguous_cases(raw_value: str) -> None:
    """非中文单日期、非法日期或日期区间都不应被误判成单日期。"""
    assert _normalize_date_ch(raw_value) is None
