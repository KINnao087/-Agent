from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


SealBBox: TypeAlias = list[int]
"""签章候选区域的外接框，格式为 [x, y, width, height]。"""


@dataclass(slots=True)
class SealCandidate:
    """单个疑似签章区域及其裁图结果。"""

    page_index: int
    image_path: str
    bbox: SealBBox
    crop_path: str | None = None
    enhanced_crop_path: str | None = None


@dataclass(slots=True)
class PartyAnchor:
    """OCR 中用于定位买方/卖方签章区域的文本锚点。"""

    page_index: int
    text: str
    role: str
    bbox: SealBBox
