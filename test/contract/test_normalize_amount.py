from __future__ import annotations

import pytest

from core.contracts.normalize import normalize_amount


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("49万元", "490000"),
        ("490,000.00元", "490000"),
        ("￥490000", "490000"),
        ("¥19万", "190000"),
        ("CNY 12,345.60", "12345.6"),
        ("1.25亿元", "125000000"),
    ],
)
def test_normalize_amount_arabic_cases(raw_value: str, expected: str) -> None:
    """阿拉伯数字金额应统一折算成以元为单位的标准字符串。"""
    assert normalize_amount(raw_value) == expected


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("人民币肆拾玖万元整", "490000"),
        ("叁拾万元", "300000"),
        ("拾万元整", "100000"),
        ("壹万贰仟叁佰肆拾伍元陆角", "12345.6"),
        ("零元", "0"),
    ],
)
def test_normalize_amount_chinese_cases(raw_value: str, expected: str) -> None:
    """中文大写金额应被正确解析并统一成以元为单位的标准字符串。"""
    assert normalize_amount(raw_value) == expected


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("", ""),
        ("   ", ""),
        ("无", ""),
        ("--", ""),
        (None, ""),
    ],
)
def test_normalize_amount_empty_like_values(raw_value: str | None, expected: str) -> None:
    """空值和无效占位值应统一归一成空字符串。"""
    assert normalize_amount(raw_value) == expected  # type: ignore[arg-type]


def test_normalize_amount_falls_back_to_cleaned_text_when_unparsed() -> None:
    """无法解析成数字金额时，返回清理后的原始文本，避免静默误判。"""
    assert normalize_amount("待确认金额") == "待确认金额"
