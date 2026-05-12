from dataclasses import dataclass, field
from typing import Literal
#CPSeal = CrossPageSeal
CPSealStatus = Literal[
    "present",      # 正常
    "missing",      # 缺失（完全没有）
    "incomplete",   # 不完整
    "unclear",      # 不清晰
    "unknown",      # 未知
]

CPSealEdge = Literal[
    "left",
    "right",
    "top",
    "bottom",
    "unknown",
]

CPSealRiskLevel = Literal[
    "low",
    "medium",
    "high",
    "unknown",
]

SealBBox = list[int]

@dataclass(slots=True)
class CPSealFragment:
    page_index: int
    image_path: str
    edge: CPSealEdge
    bbox: SealBBox
    red_area: int = 0 #红色像素点的个数
    score: float = 0.0
    crop_path: str = ""

@dataclass(slots=True)
class CPSealPageResult:
    page_index: int
    image_path: str
    fragments: list[CPSealFragment] = field(default_factory=list) #每一个对象的fragments都单独创一个list （坑）
    @property
    def has_fragments(self) -> bool:
        return bool(self.fragments)

@dataclass(slots=True)
class CPSealResult:
    status: CPSealStatus = "unknown"
    page_count: int = 0
    detected_pages: list[int] = field(default_factory=list)
    missing_pages: list[int] = field(default_factory=list)
    main_edge: CPSealEdge = "unknown"
    risk_level: CPSealRiskLevel = "unknown"
    reason: str = ""
    page_results: list[CPSealPageResult] = field(default_factory=list)