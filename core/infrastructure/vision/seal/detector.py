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
OUTPUT_DIR = Path(__file__).resolve().parents[4] / "artifacts" / "seal_candidates"
MIN_CONTOUR_AREA = 800
MIN_BBOX_WIDTH = 120
MIN_BBOX_HEIGHT = 120
MIN_BBOX_AREA = 30000
MAX_BBOX_ASPECT_RATIO = 1.6
MAX_CANDIDATES_PER_PAGE = 10
MERGE_GAP = 80


def find_red_contours(mask: MaskArray) -> list[ContourArray]:
    """从清理后的红色二值图中提取候选轮廓。
    输入是单通道 mask，输出是 OpenCV 轮廓列表。
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    result: list[ContourArray] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < MIN_CONTOUR_AREA:
            continue
        result.append(contour)

    result.sort(key=cv2.contourArea, reverse=True)
    return result


def build_candidate_bbox(contour: ContourArray) -> SealBBox:
    """根据单个轮廓生成候选区域外接框。
    输入是一条轮廓，输出是标准化的 SealBBox。
    """
    x, y, width, height = cv2.boundingRect(contour)
    return [x, y, width, height]


def _boxes_are_close(box1: SealBBox, box2: SealBBox, gap: int = MERGE_GAP) -> bool:
    """判断两个候选框是否相交或足够接近。"""
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    left1 = x1 - gap
    top1 = y1 - gap
    right1 = x1 + w1 + gap
    bottom1 = y1 + h1 + gap

    left2 = x2
    top2 = y2
    right2 = x2 + w2
    bottom2 = y2 + h2

    horizontal_overlap = not (right1 < left2 or right2 < left1)
    vertical_overlap = not (bottom1 < top2 or bottom2 < top1)
    return horizontal_overlap and vertical_overlap


def _merge_two_boxes(box1: SealBBox, box2: SealBBox) -> SealBBox:
    """把两个候选框合并成一个外接框。"""
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    left = min(x1, x2)
    top = min(y1, y2)
    right = max(x1 + w1, x2 + w2)
    bottom = max(y1 + h1, y2 + h2)
    return [left, top, right - left, bottom - top]


def merge_candidate_bboxes(boxes: list[SealBBox]) -> list[SealBBox]:
    """合并彼此相交或接近的候选框。"""
    merged = [box[:] for box in boxes]
    changed = True

    while changed:
        changed = False
        next_boxes: list[SealBBox] = []
        used = [False] * len(merged)

        for i, current in enumerate(merged):
            if used[i]:
                continue

            merged_current = current[:]
            for j in range(i + 1, len(merged)):
                if used[j]:
                    continue
                if _boxes_are_close(merged_current, merged[j]):
                    merged_current = _merge_two_boxes(merged_current, merged[j])
                    used[j] = True
                    changed = True

            used[i] = True
            next_boxes.append(merged_current)

        merged = next_boxes

    merged.sort(key=lambda box: box[2] * box[3], reverse=True)
    return merged


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
    candidate_boxes = merge_candidate_bboxes(
        [build_candidate_bbox(contour) for contour in contours]
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    candidates: list[SealCandidate] = []
    for index, bbox in enumerate(candidate_boxes):
        x, y, width, height = bbox
        bbox_area = width * height
        aspect_ratio = max(width / height, height / width)

        if width < MIN_BBOX_WIDTH or height < MIN_BBOX_HEIGHT:
            continue
        if bbox_area < MIN_BBOX_AREA:
            continue
        if aspect_ratio > MAX_BBOX_ASPECT_RATIO:
            continue

        crop = crop_bbox(image, x, y, width, height)
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

        if len(candidates) >= MAX_CANDIDATES_PER_PAGE:
            break

    return candidates
