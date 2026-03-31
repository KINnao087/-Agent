from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from core.ai import run_message_and_get_reply
import json

from core.text import linearize_ocr_page

ContinuityStatus = Literal["continuous", "discontinuous", "unknown"]
ContractPageOCR = dict[str, object]


@dataclass(slots=True)
class ContractPageText:
    """合同单页线性化文本。"""

    page_index: int
    page_text: str


@dataclass(slots=True)
class ContinuityIssue:
    """连续性问题项。"""

    page_index: int | None = None
    message: str = ""


@dataclass(slots=True)
class ContractContinuityResult:
    """合同连续性检测结果。"""

    status: ContinuityStatus = "unknown"
    reason: str = ""
    page_texts: list[ContractPageText] = field(default_factory=list)
    issues: list[ContinuityIssue] = field(default_factory=list)


def build_contract_page_texts(contract_pages: list[ContractPageOCR]) -> list[ContractPageText]:
    """把逐页 OCR 结果转换成按页线性化文本。
    后续这里直接复用 core.text.linearizer 中的逐页线性化能力。
    """
    raise NotImplementedError("TODO: build page texts from page OCR list")


def build_continuity_user_message(page_texts: list[ContractPageText]) -> str:
    """构造连续性检测提示词。
    提示词输入为 page_index -> page_text 的结构化内容。
    """
    pages_text = "\n\n".join(
        f"第{item.page_index}页：\n{item.page_text}"
        for item in page_texts
    )

    return f"""
请根据以下科技合同的逐页线性化文本，判断合同是否连续。

判断重点：
1. 相邻页之间的内容是否自然衔接。
2. 条款、段落、语义是否存在明显跳跃。
3. 是否存在疑似缺页、重复页或页面顺序异常。
4. 如果证据不足，请返回 unknown，不要臆造。

输出要求：
1. 只能输出单个 JSON 对象。
2. 不要输出解释性文字。
3. 不要输出 Markdown。
4. 返回结构必须严格如下：

{{
  "status": "continuous | discontinuous | unknown",
  "reason": "",
  "issues": [
    {{
      "page_index": 1,
      "message": ""
    }}
  ]
}}

字段说明：
- status:
  - continuous: 合同页面内容连续，未发现明显异常
  - discontinuous: 合同页面内容不连续，存在明显缺页、重复或跳跃
  - unknown: 证据不足，无法可靠判断
- reason:
  对整体判断的简要说明
- issues:
  列出发现的具体问题；如果没有问题，返回空数组

以下是合同逐页文本：
{pages_text}
""".strip()


def build_contract_continuity_result(
    data: dict,                         # ai解析后的json
    page_texts: list[ContractPageText], #线性化文本证据
) -> ContractContinuityResult:
    """把 AI 返回结果映射成连续性检测结果对象。"""
    res = ContractContinuityResult()
    res.status = data.get("status")
    res.reason = data.get("reason")
    res.page_texts = page_texts
    res.issues = data.get("issues")

    return res



def check_contract_continuity(contract_pages: list[ContractPageOCR]) -> ContractContinuityResult:
    """合同连续性检测主入口。
    负责串联逐页线性化、提示词构造、AI 审核和结果映射。
    """
    page_txt = []
    for i in range(len(contract_pages)):
        e = contract_pages[i]
        page_txt.append(
            ContractPageText(i, linearize_ocr_page(e))
        )


    ai_json = run_message_and_get_reply(user_message = build_continuity_user_message(page_txt))
    ai_data = json.loads(ai_json)
    return build_contract_continuity_result(ai_data, page_txt)
