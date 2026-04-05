from __future__ import annotations

from typing import Any

from core.infrastructure.ai.logger import get_logger
from core.infrastructure.text import build_linearized_document, parse_path_to_json_list
from core.shared.path_utils import resolve_path

logger = get_logger("ocr-payload-service")

OCRPayload = dict[str, Any]


def build_ocr_payload(
    file_path: str,
    attachments_path: str | None = None,
    invoice_path: str | None = None,
) -> OCRPayload:
    """加载合同相关文档，并组装成统一的 OCR 载荷。"""
    ocr_payload: OCRPayload = {
        "input_path": str(resolve_path(file_path)),
        "contract": parse_path_to_json_list(file_path),
        "attachments": parse_path_to_json_list(attachments_path),
        "invoice": parse_path_to_json_list(invoice_path),
    }
    ocr_payload["linearized"] = build_linearized_document(ocr_payload)

    logger.info(
        "已准备 OCR 载荷 contract_pages={}, attachments={}, invoice_pages={}, linearized_chars={}",
        len(ocr_payload["contract"]),
        len(ocr_payload["attachments"]),
        len(ocr_payload["invoice"]),
        len(ocr_payload["linearized"]["full_text"]),
    )
    return ocr_payload
