from __future__ import annotations

from core.contracts.compare import get_by_path, set_by_path


def test_get_by_path_returns_top_level_value() -> None:
    """顶层路径应直接返回对应字段值。"""
    data = {
        "contract_no": "HT-2025-001",
        "project_name": "小动物PET时间符合电子学研制",
    }

    assert get_by_path(data, "contract_no") == "HT-2025-001"


def test_get_by_path_returns_nested_value() -> None:
    """嵌套路径应返回最深层字段值。"""
    data = {
        "seller": {
            "name": "中国科学技术大学",
            "project_leader": "常进",
        }
    }

    assert get_by_path(data, "seller.name") == "中国科学技术大学"
    assert get_by_path(data, "seller.project_leader") == "常进"


def test_get_by_path_returns_empty_string_when_top_level_key_is_missing() -> None:
    """顶层字段不存在时应返回空字符串，而不是抛异常。"""
    data = {
        "seller": {
            "name": "中国科学技术大学",
        }
    }

    assert get_by_path(data, "buyer.name") == ""


def test_get_by_path_returns_empty_string_when_nested_key_is_missing() -> None:
    """嵌套字段不存在时应返回空字符串。"""
    data = {
        "seller": {
            "name": "中国科学技术大学",
        }
    }

    assert get_by_path(data, "seller.agent_phone") == ""


def test_get_by_path_returns_empty_string_when_middle_level_is_not_dict() -> None:
    """中间层不是字典时应返回空字符串。"""
    data = {
        "seller": "中国科学技术大学",
    }

    assert get_by_path(data, "seller.name") == ""


def test_set_by_path_sets_top_level_value() -> None:
    """顶层路径写入时应直接落到目标字段。"""
    data: dict[str, object] = {}
    value = {
        "label": "合同编号",
        "contract_value": "HT-2025-001",
        "platform_value": "HT-2025-001",
        "status": "match",
    }

    set_by_path(data, "contract_no", value)

    assert data == {"contract_no": value}


def test_set_by_path_creates_nested_structure() -> None:
    """嵌套路径写入时应自动创建缺失的中间层。"""
    data: dict[str, object] = {}
    value = {
        "label": "卖方名称",
        "contract_value": "中国科学技术大学",
        "platform_value": "中国科学技术大学",
        "status": "match",
    }

    set_by_path(data, "seller.name", value)

    assert data == {
        "seller": {
            "name": value,
        }
    }


def test_set_by_path_overwrites_existing_value() -> None:
    """目标字段已存在时应被新值覆盖。"""
    old_value = {
        "label": "卖方名称",
        "contract_value": "旧值",
        "platform_value": "旧值",
        "status": "match",
    }
    new_value = {
        "label": "卖方名称",
        "contract_value": "中国科学技术大学",
        "platform_value": "中国科学技术大学",
        "status": "match",
    }
    data: dict[str, object] = {
        "seller": {
            "name": old_value,
        }
    }

    set_by_path(data, "seller.name", new_value)

    assert data == {
        "seller": {
            "name": new_value,
        }
    }


def test_set_by_path_preserves_existing_siblings() -> None:
    """写入一个嵌套字段时不应破坏同层其他字段。"""
    seller_name = {
        "label": "卖方名称",
        "contract_value": "中国科学技术大学",
        "platform_value": "中国科学技术大学",
        "status": "match",
    }
    seller_phone = {
        "label": "卖方法人电话",
        "contract_value": "13800000000",
        "platform_value": "13800000000",
        "status": "match",
    }
    data: dict[str, object] = {
        "seller": {
            "name": seller_name,
        }
    }

    set_by_path(data, "seller.legal_phone", seller_phone)

    assert data == {
        "seller": {
            "name": seller_name,
            "legal_phone": seller_phone,
        }
    }


def test_get_by_path_can_read_value_after_set_by_path_write() -> None:
    """同一路径在写入后应能被读取到。"""
    data: dict[str, object] = {}
    value = {
        "label": "买方经办人电话",
        "contract_value": "13600000000",
        "platform_value": "13600000000",
        "status": "match",
    }

    set_by_path(data, "buyer.agent_phone", value)

    assert get_by_path(data, "buyer.agent_phone") == value
