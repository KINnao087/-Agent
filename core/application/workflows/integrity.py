from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from core.domain.contracts.integrity_models import (
    ContractIntegrityResult,
    ContractPageOCR,
    ContractPageText,
    ContractSealIntegrityResult,
)
from core.infrastructure.contracts.integrity_review import (
    review_contract_integrity,
    review_contract_seal_integrity,
)
from core.infrastructure.text import linearize_ocr_page, parse_folder_to_json_list
from core.infrastructure.vision.seal import detect_seal_candidates
from core.infrastructure.vision.seal.models import SealCandidate


class IntegrityState(TypedDict, total=False):
    contract_path: str
    contract_pages: list[ContractPageOCR]
    page_texts: list[ContractPageText]
    seal_candidates: list[SealCandidate]
    detect_seals: bool
    review_seals: bool
    result: ContractIntegrityResult
    seal_result: ContractSealIntegrityResult


def load_contract_pages(state: IntegrityState) -> IntegrityState:
    if "contract_pages" in state:
        return {}
    path = Path(state["contract_path"])
    return {"contract_pages": parse_folder_to_json_list(path)}


def build_page_texts(state: IntegrityState) -> IntegrityState:
    return {
        "page_texts": [
            ContractPageText(page_index=index, page_text=linearize_ocr_page(page))
            for index, page in enumerate(state["contract_pages"], start=1)
        ]
    }


def collect_seal_candidates(state: IntegrityState) -> IntegrityState:
    if not state.get("detect_seals"):
        return {}
    candidates = [
        candidate
        for page_index, page in enumerate(state["contract_pages"], start=1)
        if (image_path := page.get("input_path"))
        for candidate in detect_seal_candidates(str(image_path), page_index)
    ]
    return {"seal_candidates": candidates, "review_seals": True}


def review_integrity(state: IntegrityState) -> IntegrityState:
    return {"result": review_contract_integrity(state["page_texts"])}


def route_seal_review(state: IntegrityState) -> str:
    return "review_seals" if state.get("review_seals") and state.get("seal_candidates") else "finish"


def review_seals(state: IntegrityState) -> IntegrityState:
    return {
        "seal_result": review_contract_seal_integrity(
            state["page_texts"],
            state["seal_candidates"],
        )
    }


def finish(state: IntegrityState) -> IntegrityState:
    result = state["result"]
    result.contract_seal_integrity = state.get("seal_result", ContractSealIntegrityResult())
    return {"result": result}


def _build_graph():
    graph = StateGraph(IntegrityState)
    graph.add_node("load_contract_pages", load_contract_pages)
    graph.add_node("build_page_texts", build_page_texts)
    graph.add_node("collect_seal_candidates", collect_seal_candidates)
    graph.add_node("review_integrity", review_integrity)
    graph.add_node("review_seals", review_seals)
    graph.add_node("finish", finish)
    graph.add_edge(START, "load_contract_pages")
    graph.add_edge("load_contract_pages", "build_page_texts")
    graph.add_edge("build_page_texts", "collect_seal_candidates")
    graph.add_edge("collect_seal_candidates", "review_integrity")
    graph.add_conditional_edges(
        "review_integrity",
        route_seal_review,
        {"review_seals": "review_seals", "finish": "finish"},
    )
    graph.add_edge("review_seals", "finish")
    graph.add_edge("finish", END)
    return graph.compile()


INTEGRITY_GRAPH = _build_graph()
