from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from core.infrastructure.ai.document import structure_ocr_json
from core.infrastructure.text import (
    build_linearized_document,
    parse_path_to_json_list,
    write_linearized_outputs,
)
from core.shared.path_utils import resolve_path


class DocumentState(TypedDict, total=False):
    file_path: str
    attachments_path: str | None
    invoice_path: str | None
    output_dir: str
    ocr_payload: dict[str, Any]
    structured_json: dict[str, Any]
    output_paths: dict[str, str]


def load_documents(state: DocumentState) -> DocumentState:
    payload = {
        "input_path": str(resolve_path(state["file_path"])),
        "contract": parse_path_to_json_list(state["file_path"]),
        "attachments": parse_path_to_json_list(state.get("attachments_path")),
        "invoice": parse_path_to_json_list(state.get("invoice_path")),
    }
    payload["linearized"] = build_linearized_document(payload)
    return {
        "ocr_payload": payload,
    }


def structure_documents(state: DocumentState) -> DocumentState:
    return {"structured_json": structure_ocr_json(state["ocr_payload"])}


def write_documents(state: DocumentState) -> DocumentState:
    return {
        "output_paths": write_linearized_outputs(
            state["ocr_payload"]["linearized"],
            state["output_dir"],
        )
    }


def _parse_graph():
    graph = StateGraph(DocumentState)
    graph.add_node("load_documents", load_documents)
    graph.add_node("structure_documents", structure_documents)
    graph.add_edge(START, "load_documents")
    graph.add_edge("load_documents", "structure_documents")
    graph.add_edge("structure_documents", END)
    return graph.compile()


def _linearize_graph():
    graph = StateGraph(DocumentState)
    graph.add_node("load_documents", load_documents)
    graph.add_node("write_documents", write_documents)
    graph.add_edge(START, "load_documents")
    graph.add_edge("load_documents", "write_documents")
    graph.add_edge("write_documents", END)
    return graph.compile()


PARSE_DOCUMENTS_GRAPH = _parse_graph()
LINEARIZE_DOCUMENTS_GRAPH = _linearize_graph()
