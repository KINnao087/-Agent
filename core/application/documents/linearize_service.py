from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.application.workflows.documents import LINEARIZE_DOCUMENTS_GRAPH

@dataclass(slots=True)
class LinearizeDocumentsResult:
    """一组合同文档的线性化文本输出结果。"""

    ocr_payload: dict[str, Any]
    linearized_document: dict
    output_paths: dict[str, str]


def linearize_documents(
    file_path: str,
    output_dir: str,
    attachments_path: str | None = None,
    invoice_path: str | None = None,
) -> LinearizeDocumentsResult:
    """执行 OCR 载荷装配，并写出线性化文本结果。"""
    state = LINEARIZE_DOCUMENTS_GRAPH.invoke(
        {
            "file_path": file_path,
            "attachments_path": attachments_path,
            "invoice_path": invoice_path,
            "output_dir": output_dir,
        }
    )
    ocr_payload = state["ocr_payload"]

    return LinearizeDocumentsResult(
        ocr_payload=ocr_payload,
        linearized_document=ocr_payload["linearized"],
        output_paths=state["output_paths"],
    )
