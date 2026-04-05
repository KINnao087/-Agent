from __future__ import annotations

import os
from pathlib import Path

from core.shared.path_utils import ensure_directory, list_files_by_suffix, resolve_path

from .linearizer import linearize_ocr_page
from .pdf2png import pdf2png


def parse_file_to_json(file_path: str | Path) -> dict:
    """读取单个 PNG 图片并返回 OCR JSON。"""
    path = resolve_path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")
    if not path.is_file():
        raise ValueError(f"input path is not a file: {path}")
    if path.suffix.lower() != ".png":
        raise ValueError("only .png files are supported")

    os.environ["FLAGS_use_mkldnn"] = "0"
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

    from paddleocr import PaddleOCR

    ocr = PaddleOCR(
        lang="ch",
        device="gpu",
        enable_mkldnn=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )

    results = list(ocr.predict(str(path)))
    if not results:
        return {
            "input_path": str(path),
            "rec_texts": [],
            "rec_boxes": [],
            "rec_scores": [],
        }

    result_json = dict(results[0].json)
    if "res" in result_json and isinstance(result_json["res"], dict):
        result_json = dict(result_json["res"])
    result_json["input_path"] = str(path)
    return result_json


def parse_folder_to_json_list(folder_path: str | Path | None) -> list[dict]:
    """读取目录中的 PNG 和 PDF，转成 OCR JSON 后去重返回。"""
    if not folder_path:
        return []

    folder = resolve_path(folder_path)
    png_files = list_files_by_suffix(folder, ".png")
    pdf_files = list_files_by_suffix(folder, ".pdf")

    rendered_root = ensure_directory(folder / "_pdf_pages")
    for pdf_file in pdf_files:
        pdf_png_dir = rendered_root / pdf_file.stem
        pdf2png(pdf_file, pdf_png_dir)
        png_files.extend(list_files_by_suffix(pdf_png_dir, ".png"))

    ocrjson_list = [parse_file_to_json(file_path) for file_path in png_files]
    return deduplicate_ocrjson1(ocrjson_list)


def parse_path_to_json_list(path_value: str | Path | None) -> list[dict]:
    """解析单个 PNG 或目录，并统一返回 OCR JSON 列表。"""
    if not path_value:
        return []

    path = resolve_path(path_value)
    if not path.exists():
        raise FileNotFoundError(f"input path not found: {path}")
    if path.is_file():
        return [parse_file_to_json(path)]
    if path.is_dir():
        return parse_folder_to_json_list(path)
    raise ValueError(f"unsupported input path: {path}")


def deduplicate_ocrjson2(val1: list[dict], val2: list[dict]) -> list[dict]:
    """合并两份 OCR JSON 列表并按线性化文本去重。"""
    dedup_map: dict[str, dict] = {}
    for item in val1:
        key = linearize_ocr_page(item)
        if key in dedup_map:
            continue
        dedup_map[key] = item

    for item in val2:
        key = linearize_ocr_page(item)
        if key in dedup_map:
            continue
        dedup_map[key] = item

    return list(dedup_map.values())


def deduplicate_ocrjson1(val: list[dict]) -> list[dict]:
    """对单份 OCR JSON 列表按线性化文本去重。"""
    dedup_map: dict[str, dict] = {}
    for item in val:
        key = linearize_ocr_page(item)
        if key in dedup_map:
            continue
        dedup_map[key] = item

    return list(dedup_map.values())
