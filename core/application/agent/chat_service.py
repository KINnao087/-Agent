from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from core.application.documents import linearize_documents, parse_documents_to_structured_json
from core.infrastructure.ai import AgentRunner, ConversationSession, load_agent_config
from core.infrastructure.ai.logger import get_logger
from core.infrastructure.text import pdf2png

logger = get_logger("cli-chat-service")

CLI_SHELL_SYSTEM_PROMPT = """
你是科技合同审核系统的 CLI 控制层 AI。

你的职责：
1. 理解用户自然语言请求。
2. 当用户要处理本地合同文件时，优先调用内部工具，不要假装已经处理完成。
3. 如果缺少必要参数，例如文件路径，先用一句简短中文追问。
4. 工具返回后，用简洁中文向用户总结结果，并在需要时指出输出路径。

当前可用工具：
- pdf2pngs：将单个 PDF 文件转换为 PNG 图片列表。
- parse_documents：把合同、附件、发票解析成结构化 JSON。
- linearize_documents：把合同、附件、发票线性化成文本文件。

输出协议：
1. 如果你要调用工具，优先直接发起原生 tool call。
2. 只有在原生 tool call 不可用时，才输出：
   {"type":"tool_call","name":"tool_name","arguments":{...}}
3. 如果你要对用户说话，只能输出下面两种 JSON 之一：
   {"type":"to_user","message":"..."}
   {"type":"ask_user","message":"..."}
4. 不要输出普通自然语言，不要输出 Markdown，不要输出代码块，不要在 JSON 外面包解释。

约束：
- 不要编造文件路径、文件内容、工具结果或输出路径。
- 用户给的是单个 PDF 文件路径时，可以直接调用 parse_documents / linearize_documents，
  也可以先调用 pdf2pngs 再继续处理。
- 需要线性化但用户没有指定输出目录时，允许直接调用 linearize_documents，
  系统会使用默认输出目录。
- 用户只是咨询设计、实现思路或用法时，直接返回 to_user JSON，不必调用工具。
- 回答默认使用中文，保持简洁。
""".strip()


def _build_tool_defs() -> list[dict[str, Any]]:
    """返回控制层可见的内部工具定义。"""
    return [
        {
            "type": "function",
            "function": {
                "name": "pdf2pngs",
                "description": "将单个 PDF 文件转换为 PNG 图片列表。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "待转换的 PDF 文件路径。",
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "PNG 输出目录，可选；默认输出到 PDF 所在目录下的 <pdf_stem>_pdf_pages。",
                        },
                    },
                    "required": ["file_path"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "parse_documents",
                "description": "解析合同文件、附件和发票，输出结构化 JSON。支持单个 PNG、单个 PDF 或目录路径。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "主合同文件路径，可以是 PNG 文件、PDF 文件或目录路径。",
                        },
                        "attachments_path": {
                            "type": "string",
                            "description": "附件文件路径，可选。",
                        },
                        "invoice_path": {
                            "type": "string",
                            "description": "发票文件路径，可选。",
                        },
                    },
                    "required": ["file_path"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "linearize_documents",
                "description": "将合同文件、附件和发票线性化，并写出文本文件。支持单个 PNG、单个 PDF 或目录路径。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "主合同文件路径，可以是 PNG 文件、PDF 文件或目录路径。",
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "线性化文本输出目录，可选；默认使用输入文件所在目录下的 linearized_output。",
                        },
                        "attachments_path": {
                            "type": "string",
                            "description": "附件文件路径，可选。",
                        },
                        "invoice_path": {
                            "type": "string",
                            "description": "发票文件路径，可选。",
                        },
                    },
                    "required": ["file_path"],
                    "additionalProperties": False,
                },
            },
        },
    ]


def _default_linearized_output_dir(file_path: str | Path) -> Path:
    """根据输入路径推导默认的线性化输出目录。"""
    path = Path(file_path)
    base_dir = path if path.is_dir() else path.parent
    return (base_dir / "linearized_output").resolve()


def _default_pdf_output_dir(file_path: str | Path) -> Path:
    """根据 PDF 路径推导默认的图片输出目录。"""
    pdf_path = Path(file_path)
    return (pdf_path.parent / f"{pdf_path.stem}_pdf_pages").resolve()


def _tool_parse_documents(
    file_path: str,
    attachments_path: str | None = None,
    invoice_path: str | None = None,
) -> dict[str, str]:
    """解析合同文件并把结构化结果返回给控制层 AI。"""
    result = parse_documents_to_structured_json(
        file_path=file_path,
        attachments_path=attachments_path,
        invoice_path=invoice_path,
    )
    payload = {
        "file_path": file_path,
        "attachments_path": attachments_path or "",
        "invoice_path": invoice_path or "",
        "contract_pages": len(result.ocr_payload["contract"]),
        "attachment_pages": len(result.ocr_payload["attachments"]),
        "invoice_pages": len(result.ocr_payload["invoice"]),
        "structured_json": result.structured_json,
    }
    return {"ok": True, "output": json.dumps(payload, ensure_ascii=False, indent=2)}


def _tool_linearize_documents(
    file_path: str,
    output_dir: str | None = None,
    attachments_path: str | None = None,
    invoice_path: str | None = None,
) -> dict[str, str]:
    """线性化合同文件，并返回输出路径和统计信息。"""
    final_output_dir = str(_default_linearized_output_dir(file_path)) if not output_dir else output_dir
    result = linearize_documents(
        file_path=file_path,
        output_dir=final_output_dir,
        attachments_path=attachments_path,
        invoice_path=invoice_path,
    )
    linearized = result.linearized_document
    payload = {
        "file_path": file_path,
        "output_dir": str(Path(final_output_dir).resolve()),
        "attachments_path": attachments_path or "",
        "invoice_path": invoice_path or "",
        "contract_pages": len(result.ocr_payload["contract"]),
        "attachment_pages": len(result.ocr_payload["attachments"]),
        "invoice_pages": len(result.ocr_payload["invoice"]),
        "contract_text_chars": len(linearized["contract_text"]),
        "attachment_text_chars": len(linearized["attachment_text"]),
        "invoice_text_chars": len(linearized["invoice_text"]),
        "output_paths": result.output_paths,
    }
    return {"ok": True, "output": json.dumps(payload, ensure_ascii=False, indent=2)}


def _tool_pdf2pngs(
    file_path: str,
    output_dir: str | None = None,
) -> dict[str, str]:
    """把单个 PDF 文件转换为图片序列。"""
    final_output_dir = str(_default_pdf_output_dir(file_path)) if not output_dir else output_dir
    png_paths = pdf2png(pdf_path=file_path, output_dir=final_output_dir)
    payload = {
        "file_path": file_path,
        "output_dir": str(Path(final_output_dir).resolve()),
        "page_count": len(png_paths),
        "png_paths": png_paths,
    }
    return {"ok": True, "output": json.dumps(payload, ensure_ascii=False, indent=2)}


def _build_runtime_runner(config_path: str | Path | None = None) -> AgentRunner:
    """在原始模型配置上叠加 shell 专用 prompt 和工具目录。"""
    config = load_agent_config(config_path)
    base_system = config.base_system.strip()
    merged_system = (
        f"{base_system}\n\n{CLI_SHELL_SYSTEM_PROMPT}".strip()
        if base_system
        else CLI_SHELL_SYSTEM_PROMPT
    )
    runtime_config = replace(
        config,
        base_system=merged_system,
        tool_defs=_build_tool_defs(),
    )
    tools = {
        "pdf2pngs": _tool_pdf2pngs,
        "parse_documents": _tool_parse_documents,
        "linearize_documents": _tool_linearize_documents,
    }
    return AgentRunner(config=runtime_config, tools=tools)


@dataclass(slots=True)
class CliChatService:
    runner: AgentRunner
    session: ConversationSession

    def ask(self, message: str, max_steps: int = 8) -> str:
        """执行一轮 shell 对话，并返回最终展示给用户的文本。"""
        logger.info("CLI shell received message: {}", message)
        reply, self.session = self.runner.run_and_get_reply(
            task=message,
            session=self.session,
            max_steps=max_steps,
            enable_thinking_stream=False,
        )
        reply = reply.strip()
        return reply or "任务已完成，但模型没有返回可展示的文本。"


def create_cli_chat_service(config_path: str | Path | None = "config/config.json") -> CliChatService:
    """为 shell 创建一个带初始上下文的新会话。"""
    runner = _build_runtime_runner(config_path)
    session = runner.new_session()
    return CliChatService(runner=runner, session=session)
