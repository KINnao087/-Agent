from core.domain.contracts import CPSealFragment, CPSealResult
from core.infrastructure.ai import run_image_and_get_reply


def _build_spseal_check_prompt() -> str:
    """构建骑缝章多模态复审提示词。"""
    return """
你是科技合同骑缝章复审助手。你会收到合同页面图片、规则预检结果和红色边缘候选片段信息。
你的任务不是重新做通用合同审核，而是专门判断骑缝章是否存在、是否连续、是否完整、是否清晰。

请重点观察：
1. 页面边缘是否存在骑缝章片段，通常位于 left、right、top、bottom 某一侧。
2. 候选片段是否像同一个骑缝章被分页切开后的连续部分，而不是普通落款章、红色文字、页眉页脚、表格线、手写批注或背景噪声。
3. 多页候选片段是否主要出现在同一条边 main_edge 上。
4. 是否存在某些页缺少对应边缘片段，导致骑缝章不连续。
5. 是否存在片段过小、模糊、遮挡、位置偏移过大、颜色异常等问题，导致无法可靠判断。

输入信息说明：
- rule_result 是本地规则预检结果，只能作为参考，不能盲从。
- fragments 是规则检测出的红色边缘候选片段，bbox 格式为 [x, y, width, height]。
- score 是规则候选分，不是最终结论。
- detected_pages / missing_pages 是规则预检推断出的页面集合，你可以根据图片观察修正。

状态枚举只能使用：
- present：所有合同页都能看到合理、连续的骑缝章片段。
- missing：没有看到可信的骑缝章。
- incomplete：部分页面存在骑缝章片段，但不连续或有页面缺失。
- unclear：图片质量、遮挡、候选冲突等原因导致无法可靠判断，但不能直接认定缺失。
- unknown：输入不足或无法完成判断。

风险等级只能使用：
- low：骑缝章看起来完整且连续。
- medium：存在轻微不确定、局部不清晰或少量页面疑似异常。
- high：明显缺失、不连续、边缘不一致或疑似替换页。
- unknown：无法判断。

返回要求：
1. 只返回一个 JSON 对象。
2. 不要输出 Markdown、代码块或解释性前后缀。
3. 不要臆造页面、公司名称或不存在的候选片段。
4. 如果你修正规则预检结论，必须在 reason 中说明依据。
5. page_reviews 必须按页码升序返回。

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


def review_spseal_results(fragments: list[CPSealFragment], pre_result: CPSealResult) -> CPSealResult:
    reply_text = run_image_and_get_reply(
        image_path=fragments[0].image_path,
    )