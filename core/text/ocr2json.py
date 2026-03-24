from __future__ import annotations

import os
from pathlib import Path


def parse_file_to_json(file_path: str | Path) -> dict:
    """读取一张 PNG 图片并返回 PaddleOCR 的识别结果 JSON。"""
    path = Path(file_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()

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
