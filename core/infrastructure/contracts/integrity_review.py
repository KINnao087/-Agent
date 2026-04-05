from __future__ import annotations

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
from core.infrastructure.ai import parse_json_object, run_image_and_get_reply, run_message_and_get_reply
from core.infrastructure.ai.logger import get_logger
from core.infrastructure.vision.seal.models import SealCandidate

logger = get_logger("contract-integrity-review")


def build_integrity_user_message(page_texts: list[ContractPageText]) -> str:
    """Build the prompt for contract integrity review."""
    pages_text = "\n\n".join(
        f"第{item.page_index}页：\n{item.page_text}"
        for item in page_texts
    )

    return f"""
请根据以下科技合同的逐页线性化文本，完成合同完整性校验，并只返回 JSON。

请判断以下四项：
1. contract_continuity：合同连续性
2. contract_completeness：合同完整性
3. replacement_page：是否疑似存在替换页
4. contract_clarity：合同清晰度

判断要求：
1. page_index 是当前输入的顺序编号，不代表合同原文中的实际页码。
2. 请根据相邻页内容衔接、条款延续和语义连续性判断合同连续性。
3. 请根据整体内容是否完整、是否存在明显缺页或异常判断合同完整性。
4. 请根据页面风格、内容衔接和异常痕迹判断是否疑似存在替换页。
5. 请根据文本可读性和整体可辨识程度判断合同清晰度。
6. 如果证据不足，请返回 unknown，不要臆造。

输出要求：
1. 只能输出单个 JSON 对象。
2. 不要输出解释性文字。
3. 不要输出 Markdown。
4. 返回结构必须严格如下：

{{
  "contract_continuity": {{
    "status": "continuous | discontinuous | unknown",
    "reason": "",
    "issues": [
      {{
        "page_index": 1,
        "message": ""
      }}
    ]
  }},
  "contract_completeness": {{
    "status": "complete | incomplete | unknown",
    "reason": "",
    "issues": [
      {{
        "page_index": 1,
        "message": ""
      }}
    ]
  }},
  "replacement_page": {{
    "status": "suspected | not_suspected | unknown",
    "reason": "",
    "suspected_pages": [1]
  }},
  "contract_clarity": {{
    "status": "clear | unclear | unknown",
    "reason": "",
    "score": 0.0
  }}
}}

以下是合同逐页文本：
{pages_text}
""".strip()


def build_seal_integrity_user_message(
    page_texts: list[ContractPageText],
    candidates: list[SealCandidate],
) -> str:
    """Build the multimodal prompt for seal review."""
    pages_text = "\n\n".join(
        f"第{item.page_index}页：\n{item.page_text}"
        for item in page_texts
    )
    page_index = candidates[0].page_index if candidates else 0
    image_path = candidates[0].image_path if candidates else ""
    candidate_lines = "\n".join(
        f"- candidate_index: {index}, target_bbox: {candidate.bbox}"
        for index, candidate in enumerate(candidates)
    )

    return f"""
你将收到一张合同整页图片。该页中有多个签章候选框。你必须直接观察整张图片，并结合下面的合同逐页线性化文本，对每一个候选框对应的签章分别进行审核。

页面信息：
- page_index: {page_index}
- image_path: {image_path}

候选框列表：
{candidate_lines}

规则：
1. target_bbox 的格式为 [x, y, width, height]。
2. 你必须按 candidate_index 逐个审核当前页面中的候选框。
3. owner 只能返回 seller、buyer 或 unknown。
4. owner 映射规则必须严格遵守：
   - buyer = 甲方 / 委托方 / 买方
   - seller = 乙方 / 受托方 / 卖方
5. 每个 candidate_review 只对应一个候选框，不能把同一页里更显眼的另一个章当成当前候选框的结果。
6. 默认同一页不存在同一方重复盖多个主签章。如果你识别出 buyer 或 seller 出现了多个主签章，请重新检查，并只保留最可信的那个候选归属于该方；其他候选应返回 owner="unknown" 或 present=false/null，除非有非常明确的证据证明确实存在重复主章。
7. 你必须判断每个候选框对应区域：
   - 是否存在有效签章
   - 属于 seller / buyer / unknown
   - 是否完整
   - 是否清晰可读
   - 印章一致性
   - 印章伪造风险
8. 如果发现签章被水印遮挡，或者签章周围像素与本页图片周围像素存在明显不连续、不一致、拼接感、边缘突变、局部覆盖痕迹，则应视为该签章不合法，并在 forgery_risk 中优先体现为 forged=true 或 ps_added=true 或 copy_paste=true，risk_level 不得低于 medium。
9. 如果某个候选框区域没有明确有效的签章，请返回 present=false 或 null，并说明原因。
10. 如果无法可靠判断，请返回 unknown 或 null，不要臆造。
11. 只能输出单个 JSON 对象，不要输出解释文字、代码块或 Markdown。

返回结构必须严格如下：
{{
  "candidate_reviews": [
    {{
      "candidate_index": 0,
      "owner": "seller | buyer | unknown",
      "present": true | false | null,
      "status": "intact | damaged | unclear | missing | unknown",
      "readable": true | false | null,
      "reason": "",
      "consistency": {{
        "seller_seal_consistency": "consistent | inconsistent | unknown",
        "buyer_seal_consistency": "consistent | inconsistent | unknown",
        "cross_page_seal_consistency": "consistent | inconsistent | unknown",
        "reason": ""
      }},
      "forgery_risk": {{
        "forged": true | false | null,
        "ps_added": true | false | null,
        "printed_seal": true | false | null,
        "copy_paste": true | false | null,
        "entity_mismatch": true | false | null,
        "risk_level": "low | medium | high | unknown",
        "reason": ""
      }}
    }}
  ]
}}

以下是合同逐页文本：
{pages_text}
""".strip()


def _build_issues(raw_items: object) -> list[IntegrityIssue]:
    if not isinstance(raw_items, list):
        return []

    issues: list[IntegrityIssue] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        page_index = item.get("page_index")
        issues.append(
            IntegrityIssue(
                page_index=page_index if isinstance(page_index, int) else None,
                message=str(item.get("message", "")),
            )
        )
    return issues


def _normalize_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _build_seal_consistency_result(raw_data: object) -> SealConsistencyResult:
    if not isinstance(raw_data, dict):
        raw_data = {}

    seller_status = raw_data.get("seller_seal_consistency", "unknown")
    if seller_status not in {"consistent", "inconsistent", "unknown"}:
        seller_status = "unknown"

    buyer_status = raw_data.get("buyer_seal_consistency", "unknown")
    if buyer_status not in {"consistent", "inconsistent", "unknown"}:
        buyer_status = "unknown"

    cross_page_status = raw_data.get("cross_page_seal_consistency", "unknown")
    if cross_page_status not in {"consistent", "inconsistent", "unknown"}:
        cross_page_status = "unknown"

    return SealConsistencyResult(
        seller_seal_consistency=seller_status,
        buyer_seal_consistency=buyer_status,
        cross_page_seal_consistency=cross_page_status,
        reason=str(raw_data.get("reason", "")),
    )


def _build_seal_forgery_risk_result(raw_data: object) -> SealForgeryRiskResult:
    if not isinstance(raw_data, dict):
        raw_data = {}

    risk_level = raw_data.get("risk_level", "unknown")
    if risk_level not in {"low", "medium", "high", "unknown"}:
        risk_level = "unknown"

    return SealForgeryRiskResult(
        forged=_normalize_bool(raw_data.get("forged")),
        ps_added=_normalize_bool(raw_data.get("ps_added")),
        printed_seal=_normalize_bool(raw_data.get("printed_seal")),
        copy_paste=_normalize_bool(raw_data.get("copy_paste")),
        entity_mismatch=_normalize_bool(raw_data.get("entity_mismatch")),
        risk_level=risk_level,
        reason=str(raw_data.get("reason", "")),
    )


def build_contract_integrity_result(
    data: dict[str, object],
    page_texts: list[ContractPageText],
    contract_seal_integrity: ContractSealIntegrityResult | None = None,
) -> ContractIntegrityResult:
    continuity = data.get("contract_continuity", {})
    completeness = data.get("contract_completeness", {})
    replacement_page = data.get("replacement_page", {})
    clarity = data.get("contract_clarity", {})

    if not isinstance(continuity, dict):
        continuity = {}
    if not isinstance(completeness, dict):
        completeness = {}
    if not isinstance(replacement_page, dict):
        replacement_page = {}
    if not isinstance(clarity, dict):
        clarity = {}

    continuity_status = continuity.get("status", "unknown")
    if continuity_status not in {"continuous", "discontinuous", "unknown"}:
        continuity_status = "unknown"

    completeness_status = completeness.get("status", "unknown")
    if completeness_status not in {"complete", "incomplete", "unknown"}:
        completeness_status = "unknown"

    replacement_status = replacement_page.get("status", "unknown")
    if replacement_status not in {"suspected", "not_suspected", "unknown"}:
        replacement_status = "unknown"

    clarity_status = clarity.get("status", "unknown")
    if clarity_status not in {"clear", "unclear", "unknown"}:
        clarity_status = "unknown"

    suspected_pages = replacement_page.get("suspected_pages", [])
    if not isinstance(suspected_pages, list):
        suspected_pages = []
    suspected_pages = [page for page in suspected_pages if isinstance(page, int)]

    raw_score = clarity.get("score")
    clarity_score = float(raw_score) if isinstance(raw_score, (int, float)) else None

    return ContractIntegrityResult(
        page_texts=page_texts,
        contract_continuity=ContractContinuityResult(
            status=continuity_status,
            reason=str(continuity.get("reason", "")),
            issues=_build_issues(continuity.get("issues", [])),
        ),
        contract_completeness=ContractCompletenessResult(
            status=completeness_status,
            reason=str(completeness.get("reason", "")),
            issues=_build_issues(completeness.get("issues", [])),
        ),
        replacement_page=ReplacementPageResult(
            status=replacement_status,
            reason=str(replacement_page.get("reason", "")),
            suspected_pages=suspected_pages,
        ),
        contract_clarity=ContractClarityResult(
            status=clarity_status,
            reason=str(clarity.get("reason", "")),
            score=clarity_score,
        ),
        contract_seal_integrity=contract_seal_integrity or ContractSealIntegrityResult(),
    )


def build_seal_candidate_review_result(
    data: dict[str, object],
    candidate: SealCandidate,
) -> SealCandidateReviewResult:
    owner = data.get("owner", "unknown")
    if owner not in {"seller", "buyer", "unknown"}:
        owner = "unknown"

    status = data.get("status", "unknown")
    if status not in {"intact", "damaged", "unclear", "missing", "unknown"}:
        status = "unknown"

    return SealCandidateReviewResult(
        owner=owner,
        present=_normalize_bool(data.get("present")),
        status=status,
        readable=_normalize_bool(data.get("readable")),
        reason=str(data.get("reason", "")),
        page_index=candidate.page_index,
        image_path=str(candidate.crop_path or candidate.enhanced_crop_path or candidate.image_path),
        consistency=_build_seal_consistency_result(data.get("consistency")),
        forgery_risk=_build_seal_forgery_risk_result(data.get("forgery_risk")),
    )


def _build_unknown_candidate_review(
    candidate: SealCandidate,
    reason: str,
) -> SealCandidateReviewResult:
    return SealCandidateReviewResult(
        owner="unknown",
        present=None,
        status="unknown",
        readable=None,
        reason=reason,
        page_index=candidate.page_index,
        image_path=str(candidate.crop_path or candidate.enhanced_crop_path or candidate.image_path),
    )


def _build_page_candidate_reviews(
    raw_items: object,
    candidates: list[SealCandidate],
) -> list[SealCandidateReviewResult]:
    if not isinstance(raw_items, list):
        return [
            _build_unknown_candidate_review(candidate, "AI 未返回 candidate_reviews 列表。")
            for candidate in candidates
        ]

    reviews: list[SealCandidateReviewResult] = []
    seen_indices: set[int] = set()

    for fallback_index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            continue

        candidate_index = raw_item.get("candidate_index")
        if not isinstance(candidate_index, int):
            candidate_index = fallback_index
        if candidate_index < 0 or candidate_index >= len(candidates):
            continue

        seen_indices.add(candidate_index)
        reviews.append(
            build_seal_candidate_review_result(raw_item, candidates[candidate_index])
        )

    for candidate_index, candidate in enumerate(candidates):
        if candidate_index in seen_indices:
            continue
        reviews.append(
            _build_unknown_candidate_review(candidate, "AI 未返回该候选框的审核结果。")
        )

    return reviews


def _seal_review_priority(review: SealCandidateReviewResult) -> int:
    if review.present is True and review.status == "intact" and review.readable is True:
        return 5
    if review.present is True and review.status == "intact":
        return 4
    if review.present is True and review.status == "damaged":
        return 3
    if review.present is True and review.status == "unclear":
        return 2
    if review.present is False or review.status == "missing":
        return 1
    return 0


def _merge_party_seal_result(
    owner: SealOwner,
    reviews: list[SealCandidateReviewResult],
) -> PartySealIntegrityResult:
    matched_reviews = [review for review in reviews if review.owner == owner]
    if not matched_reviews:
        return PartySealIntegrityResult()

    best_review = max(matched_reviews, key=_seal_review_priority)
    return PartySealIntegrityResult(
        present=best_review.present,
        status=best_review.status,
        readable=best_review.readable,
        reason=best_review.reason,
        page_index=best_review.page_index,
        image_path=best_review.image_path,
        consistency=best_review.consistency,
        forgery_risk=best_review.forgery_risk,
    )


def build_contract_seal_integrity_result(
    reviews: list[SealCandidateReviewResult],
) -> ContractSealIntegrityResult:
    return ContractSealIntegrityResult(
        seller_seal=_merge_party_seal_result("seller", reviews),
        buyer_seal=_merge_party_seal_result("buyer", reviews),
        candidate_reviews=reviews,
    )


def review_contract_seal_integrity(
    page_texts: list[ContractPageText],
    seal_candidates: list[SealCandidate],
) -> ContractSealIntegrityResult:
    """Review all detected seal candidates with a multimodal model."""
    if not seal_candidates:
        return ContractSealIntegrityResult()

    candidates_by_page: dict[int, list[SealCandidate]] = {}
    for candidate in seal_candidates:
        candidates_by_page.setdefault(candidate.page_index, []).append(candidate)

    reviews: list[SealCandidateReviewResult] = []
    for page_index in sorted(candidates_by_page):
        page_candidates = sorted(
            candidates_by_page[page_index],
            key=lambda item: (item.bbox[1], item.bbox[0]),
        )
        reply_text = run_image_and_get_reply(
            image_path=page_candidates[0].image_path,
            user_message=build_seal_integrity_user_message(page_texts, page_candidates),
            work_description="你是科技合同签章校验助手，必须直接观察整页图片，并根据一组候选框逐个审核签章，只返回 JSON。",
        )
        logger.info("签章审核 AI 返回：{}", reply_text)
        data = parse_json_object(reply_text)
        reviews.extend(
            _build_page_candidate_reviews(data.get("candidate_reviews"), page_candidates)
        )

    return build_contract_seal_integrity_result(reviews)


def review_contract_integrity(
    page_texts: list[ContractPageText],
) -> ContractIntegrityResult:
    """Review text-level integrity for a contract."""
    reply_text = run_message_and_get_reply(
        user_message=build_integrity_user_message(page_texts)
    )
    data = parse_json_object(reply_text)
    return build_contract_integrity_result(data=data, page_texts=page_texts)
