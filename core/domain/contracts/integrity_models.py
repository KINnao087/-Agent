from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ContinuityStatus = Literal["continuous", "discontinuous", "unknown"]
CompletenessStatus = Literal["complete", "incomplete", "unknown"]
ReplacementPageStatus = Literal["suspected", "not_suspected", "unknown"]
ClarityStatus = Literal["clear", "unclear", "unknown"]
SealIntegrityStatus = Literal["intact", "damaged", "unclear", "missing", "unknown"]
SealOwner = Literal["seller", "buyer", "unknown"]
SealConsistencyStatus = Literal["consistent", "inconsistent", "unknown"]
SealRiskLevel = Literal["low", "medium", "high", "unknown"]
ContractPageOCR = dict[str, object]


@dataclass(slots=True)
class ContractPageText:
    """Linearized text for a single contract page."""

    page_index: int
    page_text: str


@dataclass(slots=True)
class IntegrityIssue:
    """Single issue found during contract integrity review."""

    page_index: int | None = None
    message: str = ""


@dataclass(slots=True)
class ContractContinuityResult:
    """Result for continuity review."""

    status: ContinuityStatus = "unknown"
    reason: str = ""
    issues: list[IntegrityIssue] = field(default_factory=list)


@dataclass(slots=True)
class ContractCompletenessResult:
    """Result for completeness review."""

    status: CompletenessStatus = "unknown"
    reason: str = ""
    issues: list[IntegrityIssue] = field(default_factory=list)


@dataclass(slots=True)
class ReplacementPageResult:
    """Result for replacement-page review."""

    status: ReplacementPageStatus = "unknown"
    reason: str = ""
    suspected_pages: list[int] = field(default_factory=list)


@dataclass(slots=True)
class ContractClarityResult:
    """Result for clarity review."""

    status: ClarityStatus = "unknown"
    reason: str = ""
    score: float | None = None


@dataclass(slots=True)
class SealConsistencyResult:
    """Result for seal consistency review."""

    seller_seal_consistency: SealConsistencyStatus = "unknown"
    buyer_seal_consistency: SealConsistencyStatus = "unknown"
    cross_page_seal_consistency: SealConsistencyStatus = "unknown"
    reason: str = ""


@dataclass(slots=True)
class SealForgeryRiskResult:
    """Result for seal forgery risk review."""

    forged: bool | None = None
    ps_added: bool | None = None
    printed_seal: bool | None = None
    copy_paste: bool | None = None
    entity_mismatch: bool | None = None
    risk_level: SealRiskLevel = "unknown"
    reason: str = ""


@dataclass(slots=True)
class PartySealIntegrityResult:
    """Integrity result for one party seal."""

    present: bool | None = None
    status: SealIntegrityStatus = "unknown"
    readable: bool | None = None
    reason: str = ""
    page_index: int | None = None
    image_path: str = ""
    consistency: SealConsistencyResult = field(default_factory=SealConsistencyResult)
    forgery_risk: SealForgeryRiskResult = field(default_factory=SealForgeryRiskResult)


@dataclass(slots=True)
class SealCandidateReviewResult:
    """Review result for one detected seal candidate."""

    owner: SealOwner = "unknown"
    present: bool | None = None
    status: SealIntegrityStatus = "unknown"
    readable: bool | None = None
    reason: str = ""
    page_index: int | None = None
    image_path: str = ""
    consistency: SealConsistencyResult = field(default_factory=SealConsistencyResult)
    forgery_risk: SealForgeryRiskResult = field(default_factory=SealForgeryRiskResult)


@dataclass(slots=True)
class ContractSealIntegrityResult:
    """Seal integrity result for the full contract."""

    seller_seal: PartySealIntegrityResult = field(default_factory=PartySealIntegrityResult)
    buyer_seal: PartySealIntegrityResult = field(default_factory=PartySealIntegrityResult)
    candidate_reviews: list[SealCandidateReviewResult] = field(default_factory=list)


@dataclass(slots=True)
class ContractIntegrityResult:
    """Combined contract integrity result."""

    page_texts: list[ContractPageText] = field(default_factory=list)
    contract_continuity: ContractContinuityResult = field(default_factory=ContractContinuityResult)
    contract_completeness: ContractCompletenessResult = field(default_factory=ContractCompletenessResult)
    replacement_page: ReplacementPageResult = field(default_factory=ReplacementPageResult)
    contract_clarity: ContractClarityResult = field(default_factory=ContractClarityResult)
    contract_seal_integrity: ContractSealIntegrityResult = field(default_factory=ContractSealIntegrityResult)

