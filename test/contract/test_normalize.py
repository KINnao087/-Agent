from __future__ import annotations

import pytest

from core.contracts.normalize import normalize_text


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("中国科学技术大学", "中国科学技术大学"),
        ("  中国科学技术大学  ", "中国科学技术大学"),
        ("深圳\t先进\n技术研究院", "深圳 先进 技术研究院"),
        ("技术开发（委托）合同", "技术开发(委托)合同"),
        ("【附件1】", "[附件1]"),
        ("卖方名称：深圳先进技术研究院", "卖方名称:深圳先进技术研究院"),
        ("支付方式： 分期支付", "支付方式: 分期支付"),
        ("Contract No. ABC-123", "contract no. abc-123"),
        ("Mixed CASE Value", "mixed case value"),
        ("　深圳先进技术研究院　", "深圳先进技术研究院"),
    ],
)
def test_normalize_text_common_cases(raw_value: str, expected: str) -> None:
    """常规场景：去首尾空白、压缩空白、统一大小写和常见全角标点。"""
    assert normalize_text(raw_value) == expected


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("", ""),
        ("   ", ""),
        ("\t\n  \r", ""),
    ],
)
def test_normalize_text_empty_like_values(raw_value: str, expected: str) -> None:
    """边界场景：空字符串和纯空白字符应统一成空字符串。"""
    assert normalize_text(raw_value) == expected


def test_normalize_text_returns_empty_string_for_none_like_input() -> None:
    """边界场景：即使传入 None，也应稳妥返回空字符串。"""
    assert normalize_text(None) == ""  # type: ignore[arg-type]


def test_normalize_text_keeps_single_internal_spaces() -> None:
    """内部单个空格属于有效分隔，不应被误删。"""
    raw_value = "中国 科学技术大学"
    assert normalize_text(raw_value) == "中国 科学技术大学"


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("   合同编号ABC123", "合同编号abc123"),
        ("合同编号ABC123   ", "合同编号abc123"),
        ("合同   编号    ABC123", "合同 编号 abc123"),
        ("合同\t编号\tABC123", "合同 编号 abc123"),
        ("合同\n编号\r\nABC123", "合同 编号 abc123"),
        ("合同\u3000编号\u3000ABC123", "合同 编号 abc123"),
        (" \t\n合同编号ABC123\r\n ", "合同编号abc123"),
    ],
)
def test_normalize_text_removes_redundant_whitespace_characters(
    raw_value: str,
    expected: str,
) -> None:
    """冗余空白字符应被删除或折叠，避免影响文本字段比较。"""
    assert normalize_text(raw_value) == expected


def test_normalize_text_is_idempotent_for_normalized_value() -> None:
    """已归一化的文本再次归一化后结果应保持不变。"""
    normalized = "技术开发(委托)合同"
    assert normalize_text(normalized) == normalized


def test_normalize_text_does_not_remove_meaningful_symbols() -> None:
    """有业务含义的普通符号应保留，只做轻量格式统一。"""
    raw_value = "A/B测试项目-V2.0"
    assert normalize_text(raw_value) == "a/b测试项目-v2.0"
