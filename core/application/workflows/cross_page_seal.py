from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from core.domain.contracts import CPSealFragment, CPSealResult
from core.infrastructure.text import normalize_document_images
from core.infrastructure.vision.seal.cross_page_detector import (
    analyze_cross_page_seal_results,
    detect_cross_page_seal_fragments,
)
from core.infrastructure.vision.seal.cross_page_review import review_spseal_results

class CrossPageSealState(TypedDict, total=False):
    input_path: str
    image_paths: list[Path]
    fragments: list[CPSealFragment]
    pre_result: CPSealResult
    result: CPSealResult


def collect_images(state: CrossPageSealState) -> CrossPageSealState:
    return {"image_paths": normalize_document_images(state["input_path"])}


def detect_fragments(state: CrossPageSealState) -> CrossPageSealState:
    return {
        "fragments": [
            fragment
            for page_index, image_path in enumerate(state["image_paths"], start=1)
            for fragment in detect_cross_page_seal_fragments(image_path, page_index)
        ]
    }


def analyze_fragments(state: CrossPageSealState) -> CrossPageSealState:
    result = analyze_cross_page_seal_results(state["fragments"])
    result.page_count = len(state["image_paths"])
    return {"pre_result": result}


def review_fragments(state: CrossPageSealState) -> CrossPageSealState:
    return {
        "result": review_spseal_results(
            state["fragments"],
            state["pre_result"],
        )
    }


def _build_graph():
    graph = StateGraph(CrossPageSealState)
    graph.add_node("collect_images", collect_images)
    graph.add_node("detect_fragments", detect_fragments)
    graph.add_node("analyze_fragments", analyze_fragments)
    graph.add_node("review_fragments", review_fragments)
    graph.add_edge(START, "collect_images")
    graph.add_edge("collect_images", "detect_fragments")
    graph.add_edge("detect_fragments", "analyze_fragments")
    graph.add_edge("analyze_fragments", "review_fragments")
    graph.add_edge("review_fragments", END)
    return graph.compile()


CROSS_PAGE_SEAL_GRAPH = _build_graph()
