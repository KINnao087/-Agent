from __future__ import annotations

import json
from pathlib import Path

from .invoke import invoke_structured
from .prompts import OCR_STRUCTURE_PROMPT
from .schemas import OCRDocumentResult


def structure_ocr_json(ocr_payload: dict) -> dict:
    result = invoke_structured(
        OCR_STRUCTURE_PROMPT,
        OCRDocumentResult,
        {
            "file_name": Path(ocr_payload["input_path"]).name,
            "schema": json.dumps(OCRDocumentResult.model_json_schema(), ensure_ascii=False),
            "contract": json.dumps(ocr_payload["contract"], ensure_ascii=False),
            "attachments": json.dumps(ocr_payload["attachments"], ensure_ascii=False),
            "invoice": json.dumps(ocr_payload["invoice"], ensure_ascii=False),
        },
    )
    return result.model_dump()
