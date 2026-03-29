from __future__ import annotations

from dataclasses import dataclass, field

from core.vision.seal.models import PartyAnchor, SealCandidate


@dataclass(slots=True)
class ContractSealCheckResult:
    """合同签章核对结果。"""

    seller_seal_present: bool | None = None
    buyer_seal_present: bool | None = None
    seller_seal_candidates: list[SealCandidate] = field(default_factory=list)
    buyer_seal_candidates: list[SealCandidate] = field(default_factory=list)


def extract_party_anchor_boxes(page_ocr: dict, page_index: int) -> list[PartyAnchor]:
    """从单页 OCR 结果中提取买方/卖方相关文本锚点。"""
    raise NotImplementedError("TODO: locate party anchor boxes such as 甲方、乙方、委托方、受托方")


def match_seal_candidates_to_party(
    anchors: list[PartyAnchor],
    candidates: list[SealCandidate],
) -> dict[str, list[SealCandidate]]:
    """根据空间位置把签章候选区域归属到买方或卖方。"""
    raise NotImplementedError("TODO: match seal candidates to buyer or seller anchors")


def check_contract_seals(contract_pages: list[dict]) -> ContractSealCheckResult:
    """对合同页 OCR 列表做买方/卖方签章核对。"""
    raise NotImplementedError("TODO: orchestrate contract seal extraction and buyer/seller seal checking")
