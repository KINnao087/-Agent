from __future__ import annotations

from pathlib import Path

from core.shared.path_utils import resolve_path

from .input_adapter import normalize_document_images
from .linearizer import linearize_ocr_page
from .paddle_ocr import get_paddle_ocr, predict_ocr_image


def parse_file_to_json(file_path: str | Path) -> dict:
    """Run OCR for one normalized PNG image."""
    path = resolve_path(file_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() != ".png":
        raise ValueError("OCR input must be a normalized PNG image")

    return predict_ocr_image(get_paddle_ocr(), str(path))


def parse_path_to_json_list(path_value: str | Path | None) -> list[dict]:
    """Normalize supported document input and OCR every resulting PNG page."""
    if not path_value:
        return []
    results = [
        parse_file_to_json(image_path)
        for image_path in normalize_document_images(path_value)
    ]
    return deduplicate_ocrjson1(results)


def parse_folder_to_json_list(folder_path: str | Path | None) -> list[dict]:
    return parse_path_to_json_list(folder_path)


def deduplicate_ocrjson2(val1: list[dict], val2: list[dict]) -> list[dict]:
    return deduplicate_ocrjson1([*val1, *val2])


def deduplicate_ocrjson1(values: list[dict]) -> list[dict]:
    deduplicated: dict[str, dict] = {}
    for item in values:
        deduplicated.setdefault(linearize_ocr_page(item), item)
    return list(deduplicated.values())
