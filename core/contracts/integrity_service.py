from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from core.ai import run_message_and_get_reply
from core.ai.tasks import logger
from core.text import linearize_ocr_page

ContinuityStatus = Literal["continuous", "discontinuous", "unknown"]
CompletenessStatus = Literal["complete", "incomplete", "unknown"]
ReplacementPageStatus = Literal["suspected", "not_suspected", "unknown"]
ClarityStatus = Literal["clear", "unclear", "unknown"]
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
class ContractIntegrityResult:
    """合同完整性校验结果。"""

    page_texts: list[ContractPageText] = field(default_factory=list)
    contract_continuity: ContractContinuityResult = field(default_factory=ContractContinuityResult)
    contract_completeness: ContractCompletenessResult = field(default_factory=ContractCompletenessResult)
    replacement_page: ReplacementPageResult = field(default_factory=ReplacementPageResult)
    contract_clarity: ContractClarityResult = field(default_factory=ContractClarityResult)


def build_contract_page_texts(contract_pages: list[ContractPageOCR]) -> list[ContractPageText]:
    """把逐页 OCR 结果转换为逐页线性化文本。"""
    res = []
    for i in range(len(contract_pages)):
        e = contract_pages[i]
        res.append(ContractPageText(i, linearize_ocr_page(e)))

    return res


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
4. 返回结构必须严格如下(纯json)：
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


def _build_issues(raw_items: object) -> list[IntegrityIssue]:
    """把 issues 列表转换为结构化问题项。"""
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
) -> ContractIntegrityResult:
    """把 AI 返回结果映射为合同完整性校验结果。"""
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
    clarity_score = float(raw_score) if isinstance(raw_score, int | float) else None

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
    )


def check_contract_integrity(contract_pages: list[ContractPageOCR]) -> ContractIntegrityResult:
    """合同完整性校验主入口。"""
    contract_txt = build_contract_page_texts(contract_pages)

    ai_txt = run_message_and_get_reply(user_message = build_integrity_user_message(contract_txt))
    ai_dict = json.loads(ai_txt)
    return build_contract_integrity_result(data=ai_dict, page_texts=contract_txt)