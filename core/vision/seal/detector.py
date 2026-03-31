from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt

from .models import SealBBox, SealCandidate
from .preprocessing import (
    MaskArray,
    build_red_mask,
    clean_red_mask,
    crop_bbox,
    enhance_seal_crop,
    load_image,
)

ContourArray = npt.NDArray[np.int32]
OUTPUT_DIR = Path(__file__).resolve().parents[3] / "test" / "seal" / "output"


def find_red_contours(mask: MaskArray) -> list[ContourArray]:
    """从清理后的红色二值图中提取候选轮廓。
    输入是单通道 mask，输出是 OpenCV 轮廓列表。
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    result: list[ContourArray] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 100:
            continue
        result.append(contour)

    result.sort(key=cv2.contourArea, reverse=True)
    return result


def build_candidate_bbox(contour: ContourArray) -> SealBBox:
    """根据单个轮廓生成候选区域外接框。
    输入是一条轮廓，输出是标准化的 SealBBox。
    """
    x, y, width, height = cv2.boundingRect(contour)
    return SealBBox(x=x, y=y, width=width, height=height)


def detect_seal_candidates(
    image_path: str | Path,
    page_index: int = 0,
) -> list[SealCandidate]:
    """执行单页签章候选检测并输出裁图结果。
    输入是页面路径和页号，输出是 SealCandidate 列表。
    """
    image_path = Path(image_path)
    image = load_image(image_path)
    red_mask = build_red_mask(image)
    clean_mask = clean_red_mask(red_mask)
    contours = find_red_contours(clean_mask)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    candidates: list[SealCandidate] = []
    for index, contour in enumerate(contours):
        bbox = build_candidate_bbox(contour)
        crop = crop_bbox(image, bbox.x, bbox.y, bbox.width, bbox.height)
        enhanced_crop = enhance_seal_crop(crop)

        crop_path = OUTPUT_DIR / f"{image_path.stem}_page{page_index}_candidate{index}_crop.png"
        enhanced_crop_path = OUTPUT_DIR / f"{image_path.stem}_page{page_index}_candidate{index}_enhanced.png"

        if not cv2.imwrite(str(crop_path), crop):
            raise ValueError(f"failed to write crop image: {crop_path}")
        if not cv2.imwrite(str(enhanced_crop_path), enhanced_crop):
            raise ValueError(f"failed to write enhanced crop image: {enhanced_crop_path}")

        candidates.append(
            SealCandidate(
                page_index=page_index,
                image_path=str(image_path),
                bbox=bbox,
                crop_path=str(crop_path),
                enhanced_crop_path=str(enhanced_crop_path),
            )
        )

    return candidates
