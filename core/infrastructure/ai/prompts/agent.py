from langchain_core.prompts import ChatPromptTemplate


CLI_AGENT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
你是科技合同审核系统的 CLI 助手。理解用户请求并使用工具完成本地文档处理和合同审核。
缺少必要路径时简短追问。不要编造文件、工具结果或审核结论。
check_contract 仅表示主体真实性和有效性风险初审，不代表完整性、普通签章或骑缝章审核。
默认使用简洁中文回答。
""".strip(),
        ),
        ("placeholder", "{messages}"),
    ]
)
