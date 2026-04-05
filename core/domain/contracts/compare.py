from __future__ import annotations

from typing import Any

from core.domain.contracts.field_specs import FIELD_SPECS
from core.domain.contracts.models import (
    CompareFieldResult,
    ContractBasicInfo,
    ContractBasicInfoCompareResult,
    Summary,
)
from core.domain.contracts.normalize import normalize_value


def get_by_path(data: dict[str, Any], path: str) -> str:
    """按点路径读取嵌套字段，例如 seller.name。"""
    if (not path or not data): return ""

    path = path.split(".")
    item = data.get(path[0])
    for i in range(1, len(path) - 1):
        if not item or type(item) != dict: return ""
        item = item.get(path[i])
    if (len(path) == 1): return item
    return item.get(path[-1]) if item and type(item) == dict and item.get(path[-1]) else ""


def set_by_path(data: dict[str, Any], path: str, value: Any) -> None:
    """按点路径写入嵌套字段，例如 buyer.agent_phone。"""
    if not path:
        return

    parts = path.split(".")
    current = data

    for part in parts[:-1]:
        next_item = current.get(part)
        if not type(next_item) == dict:
            next_item = {}
            current[part] = next_item
        current = next_item

    current[parts[-1]] = value


def build_compare_field_result(
    label: str,
    contract_value: str,
    platform_value: str,
    normalized_contract_value: str,
    normalized_platform_value: str,
    status: str,
) -> CompareFieldResult:
    """构造单个字段的核对结果对象。"""
    return CompareFieldResult(
        label=label,
        contract_value=contract_value,
        platform_value=platform_value,
        normalized_contract_value=normalized_contract_value,
        normalized_platform_value=normalized_platform_value,
        status=status
    )


def compare_basic_info(
    contract_basic_info: ContractBasicInfo,
    platform_basic_info: ContractBasicInfo,
) -> tuple[ContractBasicInfoCompareResult, list[dict[str, Any]]]:
    """逐字段比较合同提取结果与平台结果，并返回嵌套结果和平铺结果。"""
    contract_data = (
        contract_basic_info.model_dump()
        if hasattr(contract_basic_info, "model_dump")
        else contract_basic_info
    )
    platform_data = (
        platform_basic_info.model_dump()
        if hasattr(platform_basic_info, "model_dump")
        else platform_basic_info
    )

    compare_result = {}
    flat_results = []

    for spec in FIELD_SPECS:
        path = spec.path
        label = spec.label
        kind = spec.kind

        contract_value = get_by_path(contract_data, path)
        platform_value = get_by_path(platform_data, path)

        normalized_contract_value = normalize_value(contract_value, kind)
        normalized_platform_value = normalize_value(platform_value, kind)

        if not contract_value and not platform_value:
            status = "both_empty"
        elif not contract_value:
            status = "missing_in_contract"
        elif not platform_value:
            status = "missing_in_platform"
        elif normalized_contract_value == normalized_platform_value:
            status = "match"
        else:
            status = "mismatch"

        field_result = {
            "label": label,
            "contract_value": contract_value,
            "platform_value": platform_value,
            "normalized_contract_value": normalized_contract_value,
            "normalized_platform_value": normalized_platform_value,
            "status": status,
        }

        set_by_path(compare_result, path, field_result)

        flat_results.append({
            "path": path,
            **field_result,
        })

    return ContractBasicInfoCompareResult(**compare_result), flat_results


def build_summary(flat_results: list[dict[str, Any]]) -> Summary:
    """根据平铺的字段核对结果统计 summary。"""
    summary = Summary()
    if not flat_results:
        return summary

    summary.total_fields = len(flat_results)
    for e in flat_results:
        if e.get("status") == "missing_in_contract":
            summary.missing_in_contract_fields += 1
        elif e.get("status") == "missing_in_platform":
            summary.missing_in_platform_fields += 1
        elif e.get("status") == "both_empty":
            summary.both_empty_fields += 1
        elif e.get("status") == "mismatch":
            summary.mismatched_fields += 1
            summary.mismatch_paths.append(e.get("path", ""))
        else:
            summary.matched_fields += 1

    summary.compared_fields = summary.total_fields - summary.both_empty_fields
    summary.match_rate = (
        summary.matched_fields / summary.compared_fields
        if summary.compared_fields != 0
        else 0.0
    )
    return summary
