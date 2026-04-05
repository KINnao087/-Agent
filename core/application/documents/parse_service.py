from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.infrastructure.ai import structure_ocr_json

from .ocr_payload import OCRPayload, build_ocr_payload


@dataclass(slots=True)
class ParseDocumentsResult:
    """Structured parsing result for a set of contract documents."""

    ocr_payload: OCRPayload
    structured_json: dict[str, Any]


def parse_documents_to_structured_json(
    file_path: str,
    attachments_path: str | None = None,
    invoice_path: str | None = None,
) -> ParseDocumentsResult:
    """Execute OCR payload loading and AI structuring as one application use case."""
    ocr_payload = build_ocr_payload(
        file_path=file_path,
        attachments_path=attachments_path,
        invoice_path=invoice_path,
    )
    structured_json = structure_ocr_json(ocr_payload)
    return ParseDocumentsResult(
        ocr_payload=ocr_payload,
        structured_json=structured_json,
    )

