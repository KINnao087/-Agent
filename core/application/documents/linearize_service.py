from __future__ import annotations

from dataclasses import dataclass

from core.infrastructure.text import write_linearized_outputs

from .ocr_payload import OCRPayload, build_ocr_payload


@dataclass(slots=True)
class LinearizeDocumentsResult:
    """Linearized text output for a set of contract documents."""

    ocr_payload: OCRPayload
    linearized_document: dict
    output_paths: dict[str, str]


def linearize_documents(
    file_path: str,
    output_dir: str,
    attachments_path: str | None = None,
    invoice_path: str | None = None,
) -> LinearizeDocumentsResult:
    """Execute OCR payload loading and write linearized text outputs."""
    ocr_payload = build_ocr_payload(
        file_path=file_path,
        attachments_path=attachments_path,
        invoice_path=invoice_path,
    )
    linearized_document = ocr_payload["linearized"]
    output_paths = write_linearized_outputs(linearized_document, output_dir)

    return LinearizeDocumentsResult(
        ocr_payload=ocr_payload,
        linearized_document=linearized_document,
        output_paths=output_paths,
    )

