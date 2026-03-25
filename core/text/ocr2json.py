from __future__ import annotations

import os
from pathlib import Path


def _resolve_path(path_value: str | Path) -> Path:
    """把输入路径规范化为绝对路径。"""
    path = Path(path_value)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def parse_file_to_json(file_path: str | Path) -> dict:
    """读取单个 PNG 图片并返回 PaddleOCR 的识别结果 JSON。"""
    path = _resolve_path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")
    if not path.is_file():
        raise ValueError(f"input path is not a file: {path}")
    if path.suffix.lower() != ".png":
        raise ValueError("only .png files are supported")

    # 关闭 MKLDNN 以避免当前环境下的 Paddle CPU 推理报错。
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
    """解析文件夹中的所有 PNG 图片，并返回对应的 OCR JSON 列表。"""
    if not folder_path:
        return []

    path = _resolve_path(folder_path)
    if not path.exists():
        raise FileNotFoundError(f"input folder not found: {path}")
    if not path.is_dir():
        raise ValueError(f"input path is not a directory: {path}")

    image_files = sorted(
        file_path
        for file_path in path.iterdir()
        if file_path.is_file() and file_path.suffix.lower() == ".png"
    )
    return [parse_file_to_json(file_path) for file_path in image_files]


def parse_path_to_json_list(path_value: str | Path | None) -> list[dict]:
    """解析单个 PNG 或 PNG 文件夹，并统一返回 OCR JSON 列表。"""
    if not path_value:
        return []

    path = _resolve_path(path_value)
    if not path.exists():
        raise FileNotFoundError(f"input path not found: {path}")
    if path.is_file():
        return [parse_file_to_json(path)]
    if path.is_dir():
        return parse_folder_to_json_list(path)
    raise ValueError(f"unsupported input path: {path}")
