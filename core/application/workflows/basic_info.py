from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from core.domain.contracts.compare import build_summary, compare_basic_info
from core.domain.contracts.models import (
    CheckBasicInfoResponse,
    ContractBasicInfo,
    ContractBasicInfoCompareResult,
    Summary,
)
from core.infrastructure.contracts.basic_info_extractor import extract_contract_basic_info


class BasicInfoState(TypedDict, total=False):
    contract_text: str
    platform_basic_info: ContractBasicInfo
    contract_basic_info: ContractBasicInfo
    compare_result: ContractBasicInfoCompareResult
    flat_result: list[dict]
    summary: Summary
    response: CheckBasicInfoResponse


def extract_basic_info(state: BasicInfoState) -> BasicInfoState:
    return {"contract_basic_info": extract_contract_basic_info(state["contract_text"])}


def compare_with_platform(state: BasicInfoState) -> BasicInfoState:
    compare_result, flat_result = compare_basic_info(
        state["contract_basic_info"],
        state["platform_basic_info"],
    )
    return {"compare_result": compare_result, "flat_result": flat_result}


def summarize_comparison(state: BasicInfoState) -> BasicInfoState:
    summary = build_summary(state["flat_result"])
    return {
        "summary": summary,
        "response": CheckBasicInfoResponse(
            contract_basic_info=state["contract_basic_info"],
            compare_result=state["compare_result"],
            summary=summary,
        ),
    }


def _build_graph():
    graph = StateGraph(BasicInfoState)
    graph.add_node("extract_basic_info", extract_basic_info)
    graph.add_node("compare_with_platform", compare_with_platform)
    graph.add_node("summarize_comparison", summarize_comparison)
    graph.add_edge(START, "extract_basic_info")
    graph.add_edge("extract_basic_info", "compare_with_platform")
    graph.add_edge("compare_with_platform", "summarize_comparison")
    graph.add_edge("summarize_comparison", END)
    return graph.compile()


BASIC_INFO_GRAPH = _build_graph()
