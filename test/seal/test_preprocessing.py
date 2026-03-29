from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from core.vision.seal.preprocessing import (
    build_red_mask,
    clean_red_mask,
    crop_bbox,
    enhance_seal_crop,
    load_image,
)

INPUT_DIR = Path(__file__).resolve().parent / "imgs"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def _compute_mask_bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    """从清理后的二值图中计算红色区域的最小外接框。"""
    ys, xs = np.where(mask > 0)
    if ys.size == 0 or xs.size == 0:
        raise AssertionError("cleaned mask does not contain any red region")

    x_min = int(xs.min())
    x_max = int(xs.max())
    y_min = int(ys.min())
    y_max = int(ys.max())
    return x_min, y_min, x_max - x_min + 1, y_max - y_min + 1


def test_preprocessing_pipeline_exports_outputs() -> None:
    """执行印章预处理流程，并把中间结果输出到 seal/output。"""
    image_paths = sorted(path for path in INPUT_DIR.iterdir() if path.is_file())
    assert image_paths, f"no input images found under {INPUT_DIR}"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary: list[dict] = []

    for image_path in image_paths:
        stem = image_path.stem

        image = load_image(image_path)
        assert isinstance(image, np.ndarray)
        assert image.ndim == 3
        assert image.shape[2] == 3
        assert image.dtype == np.uint8

        red_mask = build_red_mask(image)
        assert isinstance(red_mask, np.ndarray)
        assert red_mask.ndim == 2
        assert red_mask.dtype == np.uint8

        clean_mask = clean_red_mask(red_mask)
        assert isinstance(clean_mask, np.ndarray)
        assert clean_mask.ndim == 2
        assert clean_mask.dtype == np.uint8

        x, y, width, height = _compute_mask_bbox(clean_mask)
        crop = crop_bbox(image, x, y, width, height)
        assert isinstance(crop, np.ndarray)
        assert crop.ndim == 3
        assert crop.shape[2] == 3
        assert crop.dtype == np.uint8

        enhanced_crop = enhance_seal_crop(crop)
        assert isinstance(enhanced_crop, np.ndarray)
        assert enhanced_crop.ndim == 3
        assert enhanced_crop.shape[2] == 3
        assert enhanced_crop.dtype == np.uint8
        assert np.array_equal(enhanced_crop, crop)

        red_mask_path = OUTPUT_DIR / f"{stem}_red_mask.png"
        clean_mask_path = OUTPUT_DIR / f"{stem}_clean_mask.png"
        crop_path = OUTPUT_DIR / f"{stem}_crop.png"
        enhanced_crop_path = OUTPUT_DIR / f"{stem}_enhanced_crop.png"

        assert cv2.imwrite(str(red_mask_path), red_mask)
        assert cv2.imwrite(str(clean_mask_path), clean_mask)
        assert cv2.imwrite(str(crop_path), crop)
        assert cv2.imwrite(str(enhanced_crop_path), enhanced_crop)

        summary.append(
            {
                "image_name": image_path.name,
                "image_shape": list(image.shape),
                "red_mask_shape": list(red_mask.shape),
                "clean_mask_shape": list(clean_mask.shape),
                "crop_shape": list(crop.shape),
                "enhanced_crop_shape": list(enhanced_crop.shape),
                "bbox": {
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                },
                "outputs": {
                    "red_mask": str(red_mask_path),
                    "clean_mask": str(clean_mask_path),
                    "crop": str(crop_path),
                    "enhanced_crop": str(enhanced_crop_path),
                },
            }
        )

    summary_path = OUTPUT_DIR / "preprocessing_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    assert summary_path.exists()
