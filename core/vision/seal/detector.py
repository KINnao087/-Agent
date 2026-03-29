from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import SealBBox, SealCandidate
from .preprocessing import build_red_mask, clean_red_mask, crop_bbox, enhance_seal_crop, load_image


def find_red_contours(mask: Any) -> list[Any]:
    """从红色区域 mask 中查找轮廓。"""
    raise NotImplementedError("TODO: find red region contours from mask")


def build_candidate_bbox(contour: Any) -> SealBBox:
    """根据单个轮廓生成候选区域外接矩形。"""
    raise NotImplementedError("TODO: build bbox from contour")


def detect_seal_candidates(
    image_path: str | Path,
    page_index: int = 0,
) -> list[SealCandidate]:
    """检测单页图片中的红章候选区域，并输出裁图结果。"""
    raise NotImplementedError("TODO: detect red seal regions and export raw/enhanced crop images")
