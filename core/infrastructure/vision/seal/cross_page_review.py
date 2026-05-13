from __future__ import annotations

import json
from dataclasses import asdict

from core.domain.contracts import CPSealFragment, CPSealResult
from core.infrastructure.ai import parse_json_object, run_images_and_get_reply
from core.infrastructure.ai.logger import get_logger

logger = get_logger("cross-page-seal-review")


def _build_spseal_check_prompt() -> str:
    """构建骑缝章多模态复审提示词。"""
    return """
你是科技合同骑缝章复审助手。你会收到合同页面图片、规则预检结果和红色边缘候选片段信息。
你的任务不是重新做通用合同审核，而是专门判断骑缝章是否存在、是否连续、是否完整、是否清晰。

请重点观察：
1. 页面边缘是否存在骑缝章片段，通常位于 left、right、top、bottom 某一侧。
2. 候选片段是否像同一个骑缝章被分页切开后的连续部分，而不是普通落款章、红色文字、页眉页脚、表格线、手写批注或背景噪声。
3. 多页候选片段是否主要出现在同一条边 main_edge 上。
4. 所有可信片段在视觉上融合起来，是否能拼出一个完整或基本完整的印章轮廓/文字结构。
5. 是否存在片段过小、模糊、遮挡、位置偏移过大、颜色异常等问题，导致无法可靠判断。

输入信息说明：
- rule_result 是本地规则预检结果，只能作为参考，不能盲从。
- fragments 是规则检测出的红色边缘候选片段，bbox 格式为 [x, y, width, height]。
- score 是规则候选分，不是最终结论。
- detected_pages 是规则预检发现疑似骑缝章片段的页面集合。
- missing_pages 不应按 PDF 总页数机械推断。合同可能是正反面交替扫描，骑缝章只出现在正面；不要因为背面页没有骑缝章就判定高风险。

核心判断标准：
1. 不要把“检测页数少于总页数”作为主要风险依据。
2. 请把各页边缘片段当成同一枚骑缝章被拆开的碎片，判断这些碎片整体能否拼出一个完整或基本完整的章。
3. 如果碎片只出现在奇数页或偶数页，但视觉上能拼出完整章，且符合正反面交替扫描特征，应判为 present 或 unclear，不要判为 high。
4. 只有当可信片段明显缺关键部分、无法形成完整章、边缘不一致、疑似不同印章或疑似替换页时，才判为 incomplete/high。

状态枚举只能使用：
- present：所有合同页都能看到合理、连续的骑缝章片段。
- missing：没有看到可信的骑缝章。
- incomplete：存在可信片段，但所有片段融合后仍明显缺关键部分，无法拼出完整章。
- unclear：图片质量、遮挡、候选冲突等原因导致无法可靠判断，但不能直接认定缺失。
- unknown：输入不足或无法完成判断。

风险等级只能使用：
- low：骑缝章看起来完整且连续。
- medium：存在轻微不确定、局部不清晰或少量页面疑似异常。
- high：明显缺失、片段无法拼成完整章、边缘不一致或疑似替换页。
- unknown：无法判断。

返回要求：
1. 只返回一个 JSON 对象。
2. 不要输出 Markdown、代码块或解释性前后缀。
3. 不要臆造页面、公司名称或不存在的候选片段。
4. 如果你修正规则预检结论，必须在 reason 中说明依据。
5. page_reviews 必须按页码升序返回。
6. reason 必须说明“是否能由片段整体拼出完整章”，不要只复述哪些页有/没有候选。

返回结构必须严格如下：
{
  "status": "present | missing | incomplete | unclear | unknown",
  "risk_level": "low | medium | high | unknown",
  "main_edge": "left | right | top | bottom | unknown",
  "detected_pages": [1, 2],
  "missing_pages": [],
  "reason": "",
  "page_reviews": [
    {
      "page_index": 1,
      "has_cross_page_seal": true,
      "edge": "left | right | top | bottom | unknown",
      "confidence": "high | medium | low",
      "evidence": "",
      "problem": ""
    }
  ]
}
""".strip()


def _build_spseal_review_message(
    fragments: list[CPSealFragment],
    pre_result: CPSealResult,
) -> str:
    """把规则预检结果和候选片段拼进多模态复审用户消息。"""
    payload = {
        "image_order": [
            {
                "image_index": index,
                "page_index": fragment.page_index,
                "image_path": fragment.image_path,
            }
            for index, fragment in enumerate(fragments, start=1)
        ],
        "rule_result": {
            "status": pre_result.status,
            "page_count": pre_result.page_count,
            "detected_pages": pre_result.detected_pages,
            "missing_pages": pre_result.missing_pages,
            "main_edge": pre_result.main_edge,
            "risk_level": pre_result.risk_level,
            "reason": pre_result.reason,
        },
        "fragments": [asdict(fragment) for fragment in fragments],
    }
    payload_text = json.dumps(payload, ensure_ascii=False, indent=2)
    return f"{_build_spseal_check_prompt()}\n\n规则预检信息和候选片段如下：\n{payload_text}"


def review_spseal_results(fragments: list[CPSealFragment], pre_result: CPSealResult) -> CPSealResult:
    """调用多模态模型复审骑缝章规则预检结果，并合并成 CPSealResult。"""
    fragments = list(fragments or [])
    if not fragments:
        logger.warning("骑缝章复审跳过：没有可用页面图片")
        pre_result.reason = f"{pre_result.reason}；未找到可用于多模态复审的页面图片，保留规则预检结果。"
        return pre_result

    image_paths = [fragment.image_path for fragment in fragments]
    user_message = _build_spseal_review_message(
        fragments=fragments,
        pre_result=pre_result,
    )

    try:
        reply_text = run_images_and_get_reply(
            image_paths=image_paths,
            user_message=user_message,
            work_description="你是科技合同骑缝章复审助手。你必须直接观察合同页面图片，结合规则预检结果判断骑缝章是否存在、连续、完整。只返回 JSON，不要输出 Markdown 或解释性前后缀。",
        )
    except Exception as exc:
        logger.warning("骑缝章多模态复审失败: {}", exc)
        pre_result.reason = f"{pre_result.reason}；多模态复审失败：{type(exc).__name__}: {exc}"
        return pre_result

    logger.info("骑缝章复审 AI 返回：{}", reply_text)
    try:
        review_data = parse_json_object(reply_text)
    except Exception as exc:
        logger.warning("解析骑缝章复审结果失败: {}", exc)
        pre_result.reason = f"{pre_result.reason}；多模态复审结果解析失败：{type(exc).__name__}: {exc}"
        return pre_result

    review_reason = str(review_data.get("reason") or "").strip()
    if review_reason:
        reason = f"多模态复审：{review_reason}"
        if pre_result.reason:
            reason = f"{reason}；规则预检：{pre_result.reason}"
    else:
        reason = pre_result.reason

    return CPSealResult(
        status=review_data.get("status", pre_result.status),
        page_count=pre_result.page_count,
        detected_pages=review_data.get("detected_pages", pre_result.detected_pages),
        missing_pages=review_data.get("missing_pages", pre_result.missing_pages),
        main_edge=review_data.get("main_edge", pre_result.main_edge),
        risk_level=review_data.get("risk_level", pre_result.risk_level),
        reason=reason,
        page_results=pre_result.page_results,
    )
