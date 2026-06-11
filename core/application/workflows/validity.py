from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from core.infrastructure.ai import invoke_structured
from core.infrastructure.ai.prompts import VALIDITY_REVIEW_PROMPT
from core.infrastructure.ai.schemas import ValidityReviewResponse
from core.infrastructure.contracts.basic_info_extractor import extract_contract_basic_info
from core.infrastructure.web_searcher.searcher import tavily_search


class ValidityState(TypedDict, total=False):
    contract_text: str
    linearized_path: str
    search_enabled: bool
    basic_info: dict[str, Any]
    party_searches: list[dict[str, Any]]
    validity_review: dict[str, Any]


def load_contract_text(state: ValidityState) -> ValidityState:
    if state.get("contract_text"):
        return {}
    return {
        "contract_text": Path(state["linearized_path"]).read_text(
            encoding="utf-8",
        )
    }


def extract_parties(state: ValidityState) -> ValidityState:
    return {
        "basic_info": extract_contract_basic_info(
            state["contract_text"],
        ).model_dump()
    }


def search_parties(state: ValidityState) -> ValidityState:
    if not state.get("search_enabled", True):
        return {"party_searches": []}
    names = {
        state["basic_info"][role]["name"]
        for role in ("seller", "buyer")
        if state["basic_info"][role]["name"]
    }
    return {
        "party_searches": [
            {
                "party_name": name,
                "results": tavily_search(
                    q=f"{name} 工商信息 法定代表人 失信 被执行人 经营异常",
                    sdepth="advanced",
                ).get("results", []),
            }
            for name in sorted(names)
        ]
    }


def review_validity(state: ValidityState) -> ValidityState:
    response = invoke_structured(
        VALIDITY_REVIEW_PROMPT,
        ValidityReviewResponse,
        {
            "basic_info": json.dumps(state["basic_info"], ensure_ascii=False, indent=2),
            "party_searches": json.dumps(state["party_searches"], ensure_ascii=False, indent=2),
            "contract_text": state["contract_text"][:16000],
        },
    )
    return {"validity_review": response.model_dump()}


def _build_graph():
    graph = StateGraph(ValidityState)
    graph.add_node("load_contract_text", load_contract_text)
    graph.add_node("extract_parties", extract_parties)
    graph.add_node("search_parties", search_parties)
    graph.add_node("review_validity", review_validity)
    graph.add_edge(START, "load_contract_text")
    graph.add_edge("load_contract_text", "extract_parties")
    graph.add_edge("extract_parties", "search_parties")
    graph.add_edge("search_parties", "review_validity")
    graph.add_edge("review_validity", END)
    return graph.compile()


VALIDITY_GRAPH = _build_graph()
