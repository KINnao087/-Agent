from langchain_core.prompts import ChatPromptTemplate


OCR_STRUCTURE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
你是科技合同文档解析助手。综合主合同、附件和发票 OCR 内容，提取可追溯的结构化信息。
只根据输入内容作答，不臆造。合同正文与附件或发票冲突时，以合同正文为准。
金额、日期、电话和账号保留原文。缺失文本使用空字符串，缺失数组使用空数组。
返回严格符合指定 schema 的 JSON 对象，不要输出 Markdown 或解释。
""".strip(),
        ),
        (
            "human",
            """
文件名：{file_name}

目标结构：
{schema}

主合同 OCR：
{contract}

附件 OCR：
{attachments}

发票 OCR：
{invoice}
""".strip(),
        ),
    ]
)
