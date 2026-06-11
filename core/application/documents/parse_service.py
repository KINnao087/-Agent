from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.application.workflows.documents import PARSE_DOCUMENTS_GRAPH

@dataclass(slots=True)
class ParseDocumentsResult:
    """一组合同文档的结构化解析结果。"""

    ocr_payload: dict[str, Any]
    structured_json: dict[str, Any]


def parse_documents_to_structured_json(
    file_path: str,
    attachments_path: str | None = None,
    invoice_path: str | None = None,
) -> ParseDocumentsResult:
    """执行 OCR 载荷装配与 AI 结构化解析的应用用例。"""
    state = PARSE_DOCUMENTS_GRAPH.invoke(
        {
            "file_path": file_path,
            "attachments_path": attachments_path,
            "invoice_path": invoice_path,
        }
    )
    return ParseDocumentsResult(
        ocr_payload=state["ocr_payload"],
        structured_json=state["structured_json"],
    )
