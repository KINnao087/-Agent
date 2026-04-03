from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from core.ai import parse_json_object, run_image_and_get_reply, run_message_and_get_reply
from core.text import linearize_ocr_page, parse_folder_to_json_list
from core.vision.seal import detect_seal_candidates
from core.vision.seal.models import SealCandidate

ContinuityStatus = Literal["continuous", "discontinuous", "unknown"]
CompletenessStatus = Literal["complete", "incomplete", "unknown"]
ReplacementPageStatus = Literal["suspected", "not_suspected", "unknown"]
ClarityStatus = Literal["clear", "unclear", "unknown"]
SealIntegrityStatus = Literal["intact", "damaged", "unclear", "missing", "unknown"]
SealOwner = Literal["seller", "buyer", "unknown"]
ContractPageOCR = dict[str, object]


@dataclass(slots=True)
class ContractPageText:
    """合同单页线性化文本。"""

    page_index: int
    page_text: str


@dataclass(slots=True)
class IntegrityIssue:
    """校验问题项。"""

    page_index: int | None = None
    message: str = ""


@dataclass(slots=True)
class ContractContinuityResult:
    """合同连续性结果。"""

    status: ContinuityStatus = "unknown"
    reason: str = ""
    issues: list[IntegrityIssue] = field(default_factory=list)


@dataclass(slots=True)
class ContractCompletenessResult:
    """合同完整性结果。"""

    status: CompletenessStatus = "unknown"
    reason: str = ""
    issues: list[IntegrityIssue] = field(default_factory=list)


@dataclass(slots=True)
class ReplacementPageResult:
    """替换页结果。"""

    status: ReplacementPageStatus = "unknown"
    reason: str = ""
    suspected_pages: list[int] = field(default_factory=list)


@dataclass(slots=True)
class ContractClarityResult:
    """合同清晰度结果。"""

    status: ClarityStatus = "unknown"
    reason: str = ""
    score: float | None = None


@dataclass(slots=True)
class PartySealIntegrityResult:
    """单方签章结果。"""

    present: bool | None = None
    status: SealIntegrityStatus = "unknown"
    readable: bool | None = None
    reason: str = ""
    page_index: int | None = None
    image_path: str = ""


@dataclass(slots=True)
class SealCandidateReviewResult:
    """单张签章候选图审核结果。"""

    owner: SealOwner = "unknown"
    present: bool | None = None
    status: SealIntegrityStatus = "unknown"
    readable: bool | None = None
    reason: str = ""
    page_index: int | None = None
    image_path: str = ""


@dataclass(slots=True)
class ContractSealIntegrityResult:
    """合同签章完整性结果。"""

    seller_seal: PartySealIntegrityResult = field(default_factory=PartySealIntegrityResult)
    buyer_seal: PartySealIntegrityResult = field(default_factory=PartySealIntegrityResult)
    candidate_reviews: list[SealCandidateReviewResult] = field(default_factory=list)


@dataclass(slots=True)
class ContractIntegrityResult:
    """合同完整性校验结果。"""

    page_texts: list[ContractPageText] = field(default_factory=list)
    contract_continuity: ContractContinuityResult = field(default_factory=ContractContinuityResult)
    contract_completeness: ContractCompletenessResult = field(default_factory=ContractCompletenessResult)
    replacement_page: ReplacementPageResult = field(default_factory=ReplacementPageResult)
    contract_clarity: ContractClarityResult = field(default_factory=ContractClarityResult)
    contract_seal_integrity: ContractSealIntegrityResult = field(default_factory=ContractSealIntegrityResult)


def build_contract_page_texts(contract_pages: list[ContractPageOCR]) -> list[ContractPageText]:
    """把逐页 OCR 结果转换成逐页线性化文本。"""
    return [
        ContractPageText(page_index=index, page_text=linearize_ocr_page(page))
        for index, page in enumerate(contract_pages, start=1)
    ]


def build_integrity_user_message(page_texts: list[ContractPageText]) -> str:
    """构造合同完整性校验提示词。"""
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
1. page_index 是当前输入的顺序编号，不代表合同原文中的实际页码
2. 请根据相邻页内容衔接、条款延续、语义连续性判断连续性
3. 请根据整体内容是否完整、是否存在明显缺页或异常判断完整性
4. 请根据页面风格、内容衔接和异常痕迹判断是否疑似存在替换页
5. 请根据文本可读性和整体可辨识程度判断清晰度
6. 如果证据不足，请返回 unknown，不要臆造

输出要求：
1. 只能输出单个 JSON 对象
2. 不要输出解释性文字
3. 不要输出 Markdown
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
    candidate: SealCandidate,
) -> str:
    """构造签章完整性校验提示词。"""
    pages_text = "\n\n".join(
        f"第{item.page_index}页：\n{item.page_text}"
        for item in page_texts
    )

    return f"""
你将收到一张签章候选图片。你必须直接观察这张图片本身，并结合下面的合同逐页线性化文本，判断该图片中的签章更可能属于买方还是卖方，以及该签章是否存在、是否完整、是否清晰可读。

强约束：
1. 必须基于图片内容做判断，不能忽略图片
2. 不能把普通红色文字、阴影、噪声、污点误判为签章
3. 如果图片中没有明确可识别的签章，请返回 present = null 或 false，并说明原因
4. 如果无法可靠判断买方或卖方归属，请返回 owner = "unknown"
5. 如果无法可靠判断完整性或清晰度，请返回 status = "unknown" 或 "unclear"
6. 只允许输出单个 JSON 对象，不要输出解释、备注、代码块或 Markdown

候选图片信息：
- page_index: {candidate.page_index}
- image_path: {candidate.crop_path or candidate.enhanced_crop_path or candidate.image_path}

判断目标：
1. 判断图片中是否存在真实签章
2. 判断签章更可能属于 seller、buyer 还是 unknown
3. 判断签章是否完整，是否存在明显缺损、裁切、遮挡
4. 判断签章是否清晰可读

返回结构必须严格如下：
{{
  "owner": "seller | buyer | unknown",
  "present": true | false | null,
  "status": "intact | damaged | unclear | missing | unknown",
  "readable": true | false | null,
  "reason": ""
}}

以下是合同逐页文本：
{pages_text}
""".strip()


def _build_issues(raw_items: object) -> list[IntegrityIssue]:
    """把 issues 列表转换成结构化问题项。"""
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


def build_contract_integrity_result(
    data: dict[str, object],
    page_texts: list[ContractPageText],
    contract_seal_integrity: ContractSealIntegrityResult | None = None,
) -> ContractIntegrityResult:
    """把 AI 返回结果映射成合同完整性结果。"""
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
    """把单张签章图的 AI 结果映射成结构化结果。"""
    owner = data.get("owner", "unknown")
    if owner not in {"seller", "buyer", "unknown"}:
        owner = "unknown"

    status = data.get("status", "unknown")
    if status not in {"intact", "damaged", "unclear", "missing", "unknown"}:
        status = "unknown"

    present = data.get("present")
    if not isinstance(present, bool):
        present = None

    readable = data.get("readable")
    if not isinstance(readable, bool):
        readable = None

    return SealCandidateReviewResult(
        owner=owner,
        present=present,
        status=status,
        readable=readable,
        reason=str(data.get("reason", "")),
        page_index=candidate.page_index,
        image_path=str(candidate.crop_path or candidate.enhanced_crop_path or candidate.image_path),
    )


def _seal_review_priority(review: SealCandidateReviewResult) -> int:
    """给签章审核结果打优先级。"""
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
    """从候选审核结果中汇总某一方签章结果。"""
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
    )


def build_contract_seal_integrity_result(
    reviews: list[SealCandidateReviewResult],
) -> ContractSealIntegrityResult:
    """把多张签章审核结果汇总成合同签章结果。"""
    return ContractSealIntegrityResult(
        seller_seal=_merge_party_seal_result("seller", reviews),
        buyer_seal=_merge_party_seal_result("buyer", reviews),
        candidate_reviews=reviews,
    )


def check_contract_seal_integrity(
    page_texts: list[ContractPageText],
    seal_candidates: list[SealCandidate],
) -> ContractSealIntegrityResult:
    """调用多模态模型审核签章候选图。"""
    if not seal_candidates:
        return ContractSealIntegrityResult()

    reviews: list[SealCandidateReviewResult] = []
    for candidate in seal_candidates:
        image_path = candidate.crop_path or candidate.enhanced_crop_path or candidate.image_path
        reply_text = run_image_and_get_reply(
            image_path=image_path,
            user_message=build_seal_integrity_user_message(page_texts, candidate),
            work_description="你是科技合同签章校验助手，必须直接观察图片内容判断，并且只返回 JSON。",
        )
        data = parse_json_object(reply_text)
        reviews.append(build_seal_candidate_review_result(data, candidate))

    return build_contract_seal_integrity_result(reviews)


def check_contract_integrity(
    contract_pages: list[ContractPageOCR],
    seal_candidates: list[SealCandidate] | None = None,
) -> ContractIntegrityResult:
    """合同完整性校验主入口。"""
    page_texts = build_contract_page_texts(contract_pages)
    reply_text = run_message_and_get_reply(
        user_message=build_integrity_user_message(page_texts)
    )
    data = parse_json_object(reply_text)

    contract_seal_integrity = ContractSealIntegrityResult()
    if seal_candidates:
        contract_seal_integrity = check_contract_seal_integrity(page_texts, seal_candidates)

    return build_contract_integrity_result(
        data=data,
        page_texts=page_texts,
        contract_seal_integrity=contract_seal_integrity,
    )


def _collect_seal_candidates(contract_pages: list[dict[str, object]]) -> list[SealCandidate]:
    """对整份合同所有页面做签章候选检测。"""
    candidates: list[SealCandidate] = []
    for page_index, page in enumerate(contract_pages, start=1):
        image_path = page.get("input_path")
        if not isinstance(image_path, str) or not image_path:
            continue
        candidates.extend(
            detect_seal_candidates(image_path=image_path, page_index=page_index)
        )
    return candidates


def check_contract_all(contract_path: str | Path) -> ContractIntegrityResult:
    """从合同目录直接完成文字和签章完整性校验。"""
    contract_dir = Path(contract_path)
    if not contract_dir.exists():
        raise FileNotFoundError(contract_dir)
    if not contract_dir.is_dir():
        raise NotADirectoryError(contract_dir)

    contract_pages = parse_folder_to_json_list(contract_dir)
    seal_candidates = _collect_seal_candidates(contract_pages)
    return check_contract_integrity(contract_pages, seal_candidates)
