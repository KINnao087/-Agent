from __future__ import annotations

from collections import defaultdict

from core.domain.contracts.integrity_models import (
    ContractClarityResult,
    ContractCompletenessResult,
    ContractContinuityResult,
    ContractIntegrityResult,
    ContractPageText,
    ContractSealIntegrityResult,
    IntegrityIssue,
    PartySealIntegrityResult,
    ReplacementPageResult,
    SealCandidateReviewResult,
    SealConsistencyResult,
    SealForgeryRiskResult,
    SealOwner,
)
from core.infrastructure.ai import invoke_structured
from core.infrastructure.ai.prompts import CONTRACT_INTEGRITY_PROMPT, SEAL_REVIEW_PROMPT
from core.infrastructure.ai.schemas import (
    IntegrityReviewResponse,
    SealCandidateResponse,
    SealPageReviewResponse,
)
from core.infrastructure.vision.seal.models import SealCandidate


def _pages_text(page_texts: list[ContractPageText]) -> str:
    return "\n\n".join(
        f"第{page.page_index}页：\n{page.page_text}"
        for page in page_texts
    )


def _integrity_result(
    response: IntegrityReviewResponse,
    page_texts: list[ContractPageText],
) -> ContractIntegrityResult:
    return ContractIntegrityResult(
        page_texts=page_texts,
        contract_continuity=ContractContinuityResult(
            status=response.contract_continuity.status,
            reason=response.contract_continuity.reason,
            issues=[
                IntegrityIssue(page_index=item.page_index, message=item.message)
                for item in response.contract_continuity.issues
            ],
        ),
        contract_completeness=ContractCompletenessResult(
            status=response.contract_completeness.status,
            reason=response.contract_completeness.reason,
            issues=[
                IntegrityIssue(page_index=item.page_index, message=item.message)
                for item in response.contract_completeness.issues
            ],
        ),
        replacement_page=ReplacementPageResult(
            status=response.replacement_page.status,
            reason=response.replacement_page.reason,
            suspected_pages=response.replacement_page.suspected_pages,
        ),
        contract_clarity=ContractClarityResult(
            status=response.contract_clarity.status,
            reason=response.contract_clarity.reason,
            score=response.contract_clarity.score,
        ),
    )


def review_contract_integrity(
    page_texts: list[ContractPageText],
) -> ContractIntegrityResult:
    response = invoke_structured(
        CONTRACT_INTEGRITY_PROMPT,
        IntegrityReviewResponse,
        {"pages_text": _pages_text(page_texts)},
    )
    return _integrity_result(response, page_texts)


def _candidate_result(
    response: SealCandidateResponse,
    candidate: SealCandidate,
) -> SealCandidateReviewResult:
    return SealCandidateReviewResult(
        owner=response.owner,
        present=response.present,
        status=response.status,
        readable=response.readable,
        reason=response.reason,
        page_index=candidate.page_index,
        image_path=str(candidate.crop_path or candidate.enhanced_crop_path or candidate.image_path),
        consistency=SealConsistencyResult(**response.consistency.model_dump()),
        forgery_risk=SealForgeryRiskResult(**response.forgery_risk.model_dump()),
    )


def _review_page(
    page_texts: list[ContractPageText],
    candidates: list[SealCandidate],
) -> list[SealCandidateReviewResult]:
    ordered = sorted(candidates, key=lambda item: (item.bbox[1], item.bbox[0]))
    response = invoke_structured(
        SEAL_REVIEW_PROMPT,
        SealPageReviewResponse,
        {
            "page_index": ordered[0].page_index,
            "candidates": "\n".join(
                f"{index}: {candidate.bbox}"
                for index, candidate in enumerate(ordered)
            ),
            "pages_text": _pages_text(page_texts),
        },
        image_paths=[ordered[0].image_path],
    )
    by_index = {item.candidate_index: item for item in response.candidate_reviews}
    return [
        _candidate_result(by_index[index], candidate)
        if index in by_index
        else SealCandidateReviewResult(
            page_index=candidate.page_index,
            image_path=str(candidate.image_path),
            reason="模型未返回该候选框的审核结果。",
        )
        for index, candidate in enumerate(ordered)
    ]


def _priority(review: SealCandidateReviewResult) -> int:
    return {
        (True, "intact", True): 5,
        (True, "intact", False): 4,
        (True, "damaged", False): 3,
        (True, "unclear", False): 2,
        (False, "missing", False): 1,
    }.get((review.present, review.status, bool(review.readable)), 0)


def _party_result(
    owner: SealOwner,
    reviews: list[SealCandidateReviewResult],
) -> PartySealIntegrityResult:
    matches = [review for review in reviews if review.owner == owner]
    if not matches:
        return PartySealIntegrityResult()
    best = max(matches, key=_priority)
    return PartySealIntegrityResult(
        present=best.present,
        status=best.status,
        readable=best.readable,
        reason=best.reason,
        page_index=best.page_index,
        image_path=best.image_path,
        consistency=best.consistency,
        forgery_risk=best.forgery_risk,
    )


def review_contract_seal_integrity(
    page_texts: list[ContractPageText],
    seal_candidates: list[SealCandidate],
) -> ContractSealIntegrityResult:
    candidates_by_page: dict[int, list[SealCandidate]] = defaultdict(list)
    for candidate in seal_candidates:
        candidates_by_page[candidate.page_index].append(candidate)

    reviews = [
        review
        for page_index in sorted(candidates_by_page)
        for review in _review_page(page_texts, candidates_by_page[page_index])
    ]
    return ContractSealIntegrityResult(
        seller_seal=_party_result("seller", reviews),
        buyer_seal=_party_result("buyer", reviews),
        candidate_reviews=reviews,
    )
