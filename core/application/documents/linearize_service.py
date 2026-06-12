from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.infrastructure.text import write_linearized_outputs

from ._loader import load_document_payload

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
    ocr_payload = load_document_payload(
        file_path,
        attachments_path,
        invoice_path,
    )

    return LinearizeDocumentsResult(
        ocr_payload=ocr_payload,
        linearized_document=ocr_payload["linearized"],
        output_paths=write_linearized_outputs(
            ocr_payload["linearized"],
            output_dir,
        ),
    )
