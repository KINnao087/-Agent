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
    """单个合同页面的线性化文本。"""

    page_index: int
    page_text: str


@dataclass(slots=True)
class IntegrityIssue:
    """合同完整性审核中发现的单个问题。"""

    page_index: int | None = None
    message: str = ""


@dataclass(slots=True)
class ContractContinuityResult:
    """合同连续性审核结果。"""

    status: ContinuityStatus = "unknown"
    reason: str = ""
    issues: list[IntegrityIssue] = field(default_factory=list)


@dataclass(slots=True)
class ContractCompletenessResult:
    """合同完整性审核结果。"""

    status: CompletenessStatus = "unknown"
    reason: str = ""
    issues: list[IntegrityIssue] = field(default_factory=list)


@dataclass(slots=True)
class ReplacementPageResult:
    """替换页审核结果。"""

    status: ReplacementPageStatus = "unknown"
    reason: str = ""
    suspected_pages: list[int] = field(default_factory=list)


@dataclass(slots=True)
class ContractClarityResult:
    """合同清晰度审核结果。"""

    status: ClarityStatus = "unknown"
    reason: str = ""
    score: float | None = None


@dataclass(slots=True)
class SealConsistencyResult:
    """印章一致性审核结果。"""

    seller_seal_consistency: SealConsistencyStatus = "unknown"
    buyer_seal_consistency: SealConsistencyStatus = "unknown"
    cross_page_seal_consistency: SealConsistencyStatus = "unknown"
    reason: str = ""


@dataclass(slots=True)
class SealForgeryRiskResult:
    """印章伪造风险审核结果。"""

    forged: bool | None = None
    ps_added: bool | None = None
    printed_seal: bool | None = None
    copy_paste: bool | None = None
    entity_mismatch: bool | None = None
    risk_level: SealRiskLevel = "unknown"
    reason: str = ""


@dataclass(slots=True)
class PartySealIntegrityResult:
    """单方印章完整性结果。"""

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
    """单个检测到的印章候选审核结果。"""

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
    """整份合同的印章完整性结果。"""

    seller_seal: PartySealIntegrityResult = field(default_factory=PartySealIntegrityResult)
    buyer_seal: PartySealIntegrityResult = field(default_factory=PartySealIntegrityResult)
    candidate_reviews: list[SealCandidateReviewResult] = field(default_factory=list)


@dataclass(slots=True)
class ContractIntegrityResult:
    """合同完整性综合审核结果。"""

    page_texts: list[ContractPageText] = field(default_factory=list)
    contract_continuity: ContractContinuityResult = field(default_factory=ContractContinuityResult)
    contract_completeness: ContractCompletenessResult = field(default_factory=ContractCompletenessResult)
    replacement_page: ReplacementPageResult = field(default_factory=ReplacementPageResult)
    contract_clarity: ContractClarityResult = field(default_factory=ContractClarityResult)
    contract_seal_integrity: ContractSealIntegrityResult = field(default_factory=ContractSealIntegrityResult)
