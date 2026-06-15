from langchain_core.prompts import ChatPromptTemplate


BASIC_INFO_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
你是科技合同基本信息提取助手。只根据合同原文提取信息，不臆造，不标准化原文。
结合上下文将甲方/委托方映射为 buyer，将乙方/受托方映射为 seller；正文明确相反关系时以正文为准。
返回严格符合 schema 的 JSON 对象，不要输出 Markdown 或解释。
""".strip(),
        ),
        ("human", "合同文本：\n{contract_text}"),
    ]
)


CONTRACT_INTEGRITY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
你是科技合同完整性审核助手。根据逐页文本判断内容连续性、完整性、替换页风险和清晰度。
page_index 仅表示输入顺序。证据不足时返回 unknown，不臆造。
返回严格符合 schema 的 JSON 对象，不要输出 Markdown 或解释。
""".strip(),
        ),
        ("human", "合同逐页文本：\n{pages_text}"),
    ]
)


SEAL_REVIEW_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
你是科技合同签章审核助手。直接观察整页图片，并结合合同文本逐个审核候选框。
buyer 对应甲方/委托方/买方，seller 对应乙方/受托方/卖方。
检查签章是否存在、完整、清晰、一致，以及伪造、PS、打印和复制粘贴风险。
候选证据不足时返回 unknown。返回严格符合 schema 的 JSON，不要输出解释。
""".strip(),
        ),
        (
            "human",
            """
页面：{page_index}
候选框，bbox 格式为 [x, y, width, height]：
{candidates}

合同逐页文本：
{pages_text}
""".strip(),
        ),
    ]
)


CROSS_PAGE_SEAL_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
你是科技合同骑缝章复审助手。直接观察页面图片，结合规则预检和红色边缘候选片段，
判断片段整体能否拼成完整、连续的同一枚骑缝章。
不要机械地因为部分背面页无候选就判定高风险。证据不足时返回 unclear 或 unknown。
返回严格符合 schema 的 JSON，不要输出 Markdown 或解释。
""".strip(),
        ),
        ("human", "规则预检和候选片段：\n{payload}"),
    ]
)


VALIDITY_REVIEW_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
你是科技合同有效性风险审核助手。你的结论是审核风险意见，不是法院裁判。
必须结合合同原文、主体信息和公开搜索证据；搜索不足时明确说明无法确认。
返回严格符合 schema 的 JSON，不要输出 Markdown 或解释。
""".strip(),
        ),
        (
            "human",
            """
合同基本信息：
{basic_info}

主体搜索结果：
{party_searches}

合同文本：
{contract_text}
""".strip(),
        ),
    ]
)
