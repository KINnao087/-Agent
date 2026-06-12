from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.infrastructure.ai.document import structure_ocr_json

from ._loader import load_document_payload

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
    ocr_payload = load_document_payload(
        file_path,
        attachments_path,
        invoice_path,
    )
    return ParseDocumentsResult(
        ocr_payload=ocr_payload,
        structured_json=structure_ocr_json(ocr_payload),
    )
