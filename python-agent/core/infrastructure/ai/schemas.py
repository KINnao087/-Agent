from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class OCRDocumentResult(BaseModel):
    doc_id: str = ""
    source: dict[str, Any] = Field(default_factory=dict)
    processing: dict[str, Any] = Field(default_factory=dict)
    raw_content: dict[str, Any] = Field(default_factory=dict)
    structured: dict[str, Any] = Field(default_factory=dict)


class IntegrityIssueResponse(BaseModel):
    page_index: int | None = None
    message: str = ""


class ContinuityResponse(BaseModel):
    status: Literal["continuous", "discontinuous", "unknown"] = "unknown"
    reason: str = ""
    issues: list[IntegrityIssueResponse] = Field(default_factory=list)


class CompletenessResponse(BaseModel):
    status: Literal["complete", "incomplete", "unknown"] = "unknown"
    reason: str = ""
    issues: list[IntegrityIssueResponse] = Field(default_factory=list)


class ReplacementPageResponse(BaseModel):
    status: Literal["suspected", "not_suspected", "unknown"] = "unknown"
    reason: str = ""
    suspected_pages: list[int] = Field(default_factory=list)


class ClarityResponse(BaseModel):
    status: Literal["clear", "unclear", "unknown"] = "unknown"
    reason: str = ""
    score: float | None = None


class IntegrityReviewResponse(BaseModel):
    contract_continuity: ContinuityResponse = Field(default_factory=ContinuityResponse)
    contract_completeness: CompletenessResponse = Field(default_factory=CompletenessResponse)
    replacement_page: ReplacementPageResponse = Field(default_factory=ReplacementPageResponse)
    contract_clarity: ClarityResponse = Field(default_factory=ClarityResponse)


class SealConsistencyResponse(BaseModel):
    seller_seal_consistency: Literal["consistent", "inconsistent", "unknown"] = "unknown"
    buyer_seal_consistency: Literal["consistent", "inconsistent", "unknown"] = "unknown"
    cross_page_seal_consistency: Literal["consistent", "inconsistent", "unknown"] = "unknown"
    reason: str = ""


class SealForgeryRiskResponse(BaseModel):
    forged: bool | None = None
    ps_added: bool | None = None
    printed_seal: bool | None = None
    copy_paste: bool | None = None
    entity_mismatch: bool | None = None
    risk_level: Literal["low", "medium", "high", "unknown"] = "unknown"
    reason: str = ""


class SealCandidateResponse(BaseModel):
    candidate_index: int
    owner: Literal["seller", "buyer", "unknown"] = "unknown"
    present: bool | None = None
    status: Literal["intact", "damaged", "unclear", "missing", "unknown"] = "unknown"
    readable: bool | None = None
    visible_company_name: str = ""
    reason: str = ""
    consistency: SealConsistencyResponse = Field(default_factory=SealConsistencyResponse)
    forgery_risk: SealForgeryRiskResponse = Field(default_factory=SealForgeryRiskResponse)


class SealPageReviewResponse(BaseModel):
    candidate_reviews: list[SealCandidateResponse] = Field(default_factory=list)


class CrossPageReviewItem(BaseModel):
    page_index: int
    has_cross_page_seal: bool
    edge: Literal["left", "right", "top", "bottom", "unknown"] = "unknown"
    confidence: Literal["high", "medium", "low"] = "low"
    evidence: str = ""
    problem: str = ""


class CrossPageSealReviewResponse(BaseModel):
    status: Literal["present", "missing", "incomplete", "unclear", "unknown"] = "unknown"
    risk_level: Literal["low", "medium", "high", "unknown"] = "unknown"
    main_edge: Literal["left", "right", "top", "bottom", "unknown"] = "unknown"
    detected_pages: list[int] = Field(default_factory=list)
    missing_pages: list[int] = Field(default_factory=list)
    reason: str = ""
    page_reviews: list[CrossPageReviewItem] = Field(default_factory=list)


class ValidityEvidence(BaseModel):
    item: str = ""
    evidence: str = ""
    risk: Literal["none", "low", "medium", "high", "unknown"] = "unknown"


class PartySearchEvidence(BaseModel):
    party: str = ""
    evidence: str = ""
    risk: Literal["none", "low", "medium", "high", "unknown"] = "unknown"
    source_urls: list[str] = Field(default_factory=list)


class ValidityReviewResponse(BaseModel):
    conclusion: Literal["likely_valid", "validity_risk", "likely_invalid", "unknown"] = "unknown"
    summary: str = ""
    contract_evidence: list[ValidityEvidence] = Field(default_factory=list)
    party_search_evidence: list[PartySearchEvidence] = Field(default_factory=list)
    risk_points: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
