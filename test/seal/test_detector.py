from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from core.vision.seal.detector import (
    build_candidate_bbox,
    detect_seal_candidates,
    find_red_contours,
)
from core.vision.seal.models import SealBBox, SealCandidate

INPUT_DIR = Path(__file__).resolve().parent / "imgs"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def _build_test_mask() -> np.ndarray:
    """构造包含两个有效区域和一个小噪点的测试二值图。"""
    mask = np.zeros((200, 240), dtype=np.uint8)
    cv2.rectangle(mask, (10, 20), (70, 100), 255, thickness=-1)
    cv2.rectangle(mask, (140, 60), (210, 150), 255, thickness=-1)
    cv2.rectangle(mask, (5, 5), (10, 10), 255, thickness=-1)
    return mask


def test_find_red_contours_returns_multiple_large_regions() -> None:
    """应提取多个有效轮廓，并过滤掉面积过小的噪点。"""
    mask = _build_test_mask()

    contours = find_red_contours(mask)

    assert isinstance(contours, list)
    assert len(contours) == 2
    assert all(isinstance(contour, np.ndarray) for contour in contours)


def test_build_candidate_bbox_returns_expected_box() -> None:
    """应根据轮廓生成正确的外接框。"""
    mask = np.zeros((100, 100), dtype=np.uint8)
    cv2.rectangle(mask, (20, 30), (50, 70), 255, thickness=-1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bbox = build_candidate_bbox(contours[0])

    assert isinstance(bbox, SealBBox)
    assert bbox.x == 20
    assert bbox.y == 30
    assert bbox.width == 31
    assert bbox.height == 41


def test_detect_seal_candidates_returns_candidates_for_real_image() -> None:
    """对真实样例图应能返回候选签章列表。"""
    image_path = INPUT_DIR / "seal2.png"

    candidates = detect_seal_candidates(image_path=image_path, page_index=3)

    assert isinstance(candidates, list)
    assert candidates
    assert all(isinstance(candidate, SealCandidate) for candidate in candidates)
    assert all(candidate.page_index == 3 for candidate in candidates)
    assert all(candidate.image_path == str(image_path) for candidate in candidates)

    for candidate in candidates:
        assert candidate.bbox.width > 0
        assert candidate.bbox.height > 0
        assert candidate.bbox.x >= 0
        assert candidate.bbox.y >= 0
        assert candidate.crop_path is not None
        assert candidate.enhanced_crop_path is not None
        assert Path(candidate.crop_path).exists()
        assert Path(candidate.enhanced_crop_path).exists()
        assert Path(candidate.crop_path).parent == OUTPUT_DIR
        assert Path(candidate.enhanced_crop_path).parent == OUTPUT_DIR
