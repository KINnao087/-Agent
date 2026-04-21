from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from core.application.documents import linearize_documents, parse_documents_to_structured_json
from core.infrastructure.ai import AgentRunner, ConversationSession, load_agent_config
from core.infrastructure.ai import parse_json_object, run_message_and_get_reply
from core.infrastructure.ai.logger import get_logger
from core.infrastructure.basetools.sys_cmds import ls as sys_ls
from core.infrastructure.basetools.sys_cmds import readfile as sys_readfile
from core.infrastructure.basetools.sys_cmds import readimage as sys_readimage
from core.infrastructure.basetools.sys_cmds import writefile as sys_writefile
from core.infrastructure.contracts.basic_info_extractor import extract_contract_basic_info
from core.infrastructure.text import pdf2png
from core.infrastructure.web_searcher.searcher import tavliy_search

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
- check_contract：对 PDF、PNG 或图片目录执行完整合同检查：OCR 线性化、抽取主体、搜索核验、判断双方公司信息真实性和可信风险。
- tavliy_search：根据查询词执行网页搜索，并返回搜索结果字典。
- review_contract_validity：读取线性化合同文本，搜索合同主体公开信息，并给出合同有效性风险判断。
- ls：列出本机目录下的文件和子目录。
- readfile：读取本机文本文件内容。
- readimage：读取本机图片文件；工具消息返回摘要，并将图片作为 image_url 附加到下一轮模型输入。
- writefile：向本机路径写入文本文件。

输出协议：
1. 如果你要调用工具，优先直接发起原生 tool call。
2. 只有在原生 tool call 不可用时，才输出：
   {"type":"tool_call","name":"tool_name","arguments":{...}}
   arguments 里的参数名必须严格使用工具定义 parameters.properties 中列出的名字。
3. 如果你要对用户说话，只能输出下面两种 JSON 之一：
   {"type":"to_user","message":"..."}
   {"type":"ask_user","message":"..."}
4. 不要输出普通自然语言，不要输出 Markdown，不要输出代码块，不要在 JSON 外面包解释。

约束：
- 不要编造文件路径、文件内容、工具结果或输出路径。
- 不要声称自己不能读取图片；对于 PNG、PDF 或图片目录，调用 check_contract 或 linearize_documents，
  工具会通过 OCR 读取图片内容。
- 用户要求“检查合同图片/PDF/目录，并判断双方公司信息是否真实、是否可信”时，
  必须优先调用 check_contract；不要先调用 pdf2pngs，也不要要求用户再提供图片路径。
- 用户给的是单个 PDF 文件路径时，可以直接调用 parse_documents / linearize_documents，
  也可以先调用 pdf2pngs 再继续处理。
- 需要线性化但用户没有指定输出目录时，允许直接调用 linearize_documents，
  系统会使用默认输出目录。
- 用户要求“根据已有线性化结果判断合同是否有效”“搜索并判断合同有效性”时，
  必须调用 review_contract_validity；不要只搜索合同有效性标准，也不要只给通用法律标准。
  如果没有明确线性化文件路径，优先使用上一轮 linearize_documents 返回的 contract_linearized.txt 路径。
- 用户要求查看目录、读取文件或写入文件时，调用 ls / readfile / writefile；
  路径可以是绝对路径，也可以是相对当前工作目录的路径。
- 用户明确要求读取单张图片原始数据时，调用 readimage；如果是合同图片文字识别或合同审核，
  优先调用 check_contract / linearize_documents，而不是直接 readimage。
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
        {
            "type": "function",
            "function": {
                "name": "check_contract",
                "description": "对 PDF、PNG 或图片目录执行完整合同检查：OCR 线性化、抽取合同主体、搜索主体公开信息、失信和经营异常，并判断双方公司信息真实性和可信风险。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "合同输入路径，可以是单个 PDF、单个 PNG 或包含合同图片/PDF 的目录。",
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "线性化文本输出目录，可选；默认使用输入路径所在目录下的 linearized_output。",
                        },
                        "attachments_path": {
                            "type": "string",
                            "description": "附件路径，可选。",
                        },
                        "invoice_path": {
                            "type": "string",
                            "description": "发票路径，可选。",
                        },
                        "search_enabled": {
                            "type": "boolean",
                            "description": "是否搜索合同主体公开信息、失信和经营异常，默认 true。",
                            "default": True,
                        },
                    },
                    "required": ["input_path"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "tavliy_search",
                "description": "根据查询词执行网页搜索，并返回搜索结果字典。不要用它单独判断合同有效性；合同有效性风险判断请调用 review_contract_validity。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词。"
                        },
                        "sdepth": {
                            "type": "string",
                            "description": "搜索深度，默认是 advanced。包括'basic', 'advanced', 'fast', 'ultra-fast'",
                            "default": "advanced"
                        }
                    },
                    "required": ["query"],
                    "additionalProperties": False
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "review_contract_validity",
                "description": "读取线性化合同文本，抽取合同主体，搜索主体公开信息、失信和经营异常风险，并基于合同文本和搜索证据给出合同有效性风险判断。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "linearized_path": {
                            "type": "string",
                            "description": "线性化合同文本路径。若用户刚刚完成线性化，应优先使用上一轮工具输出中的 contract_linearized.txt 路径。",
                        },
                        "contract_text": {
                            "type": "string",
                            "description": "可选，直接传入合同线性化文本；通常优先传 linearized_path。",
                        },
                        "search_enabled": {
                            "type": "boolean",
                            "description": "是否搜索合同主体公开信息、失信和经营异常，默认 true。",
                            "default": True,
                        },
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ls",
                "description": "列出本机目录下的文件和子目录。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "要列出的目录路径。可以是绝对路径或相对当前工作目录的路径，默认是当前目录。",
                            "default": ".",
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "是否递归列出子目录，默认 false。",
                            "default": False,
                        },
                        "max_entries": {
                            "type": "integer",
                            "description": "最多返回多少个条目，默认 200。",
                            "default": 200,
                        },
                        "include_hidden": {
                            "type": "boolean",
                            "description": "是否包含以点开头的隐藏文件，默认 true。",
                            "default": True,
                        },
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "readfile",
                "description": "读取本机文本文件内容。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "要读取的文件路径。可以是绝对路径或相对当前工作目录的路径。",
                        },
                        "encoding": {
                            "type": "string",
                            "description": "文件编码，默认 utf-8。",
                            "default": "utf-8",
                        },
                        "max_chars": {
                            "type": "integer",
                            "description": "最多读取多少个字符，默认 20000。",
                            "default": 20000,
                        },
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "readimage",
                "description": "读取本机图片文件；工具消息返回 MIME 类型、大小等摘要，并将图片以 image_url 形式附加给下一轮模型。适合把单张图片交给 AI；合同图片 OCR/审核优先使用 check_contract 或 linearize_documents。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "要读取的图片路径。支持 png、jpg、jpeg、webp、bmp、gif。",
                        },
                        "max_bytes": {
                            "type": "integer",
                            "description": "允许读取的最大图片字节数，默认 6000000。",
                            "default": 6000000,
                        },
                        "include_data_url": {
                            "type": "boolean",
                            "description": "是否生成用于 image_url 的 data URL，默认 true。",
                            "default": True,
                        },
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "writefile",
                "description": "向本机路径写入文本文件。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "要写入的文件路径。可以是绝对路径或相对当前工作目录的路径。",
                        },
                        "content": {
                            "type": "string",
                            "description": "要写入文件的文本内容。",
                        },
                        "encoding": {
                            "type": "string",
                            "description": "文件编码，默认 utf-8。",
                            "default": "utf-8",
                        },
                        "overwrite": {
                            "type": "boolean",
                            "description": "目标文件已存在时是否覆盖，默认 false。",
                            "default": False,
                        },
                        "create_parents": {
                            "type": "boolean",
                            "description": "父目录不存在时是否自动创建，默认 true。",
                            "default": True,
                        },
                    },
                    "required": ["path", "content"],
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


def _first_present(*values: str | Path | None) -> str | None:
    """返回第一个非空参数值，用于兼容模型偶尔生成的别名参数。"""
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _model_to_dict(value: Any) -> dict[str, Any]:
    """把 pydantic v1/v2 模型或普通对象转成 dict。"""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, dict):
        return value
    return {}


def _find_latest_linearized_contract() -> Path | None:
    """从当前工作目录中找最近生成的 contract_linearized.txt。"""
    candidates: list[Path] = []
    for path in Path.cwd().rglob("contract_linearized.txt"):
        if path.is_file():
            candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _search_contract_party(name: str) -> dict[str, Any]:
    """围绕合同主体搜索工商、联系方式、失信和经营异常风险。"""
    query = f"{name} 工商信息 法定代表人 联系方式 失信 被执行人 经营异常"
    try:
        result = tavliy_search(q=query, sdepth="advanced")
    except Exception as exc:
        return {
            "party_name": name,
            "query": query,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "results": [],
        }
    return {
        "party_name": name,
        "query": query,
        "ok": True,
        "results": result.get("results", []) if isinstance(result, dict) else result,
    }


def _build_validity_review_prompt(
    contract_text: str,
    basic_info: dict[str, Any],
    party_searches: list[dict[str, Any]],
) -> str:
    """构造基于合同文本和搜索证据的有效性风险审核提示词。"""
    excerpt = contract_text[:16000]
    basic_info_text = json.dumps(basic_info, ensure_ascii=False, indent=2)
    search_text = json.dumps(party_searches, ensure_ascii=False, indent=2)
    return f"""
请根据合同线性化文本、合同基本信息和主体公开信息搜索结果，判断该合同的有效性风险。

注意：
1. 这里的“有效性判断”是合同审核风险判断，不是法院裁判结论。
2. 不能只复述合同有效的一般法律标准，必须引用本合同文本中的主体、金额、日期、签章/签字、条款等具体证据。
3. 必须结合搜索结果判断合同主体是否存在身份不一致、失信被执行、经营异常、联系方式或法定代表人不一致等风险。
4. 如果搜索结果不足以确认，必须写明“未能从搜索结果确认”，不得臆造。
5. 只返回单个 JSON 对象，不要输出 Markdown。

返回结构：
{{
  "conclusion": "likely_valid | validity_risk | likely_invalid | unknown",
  "summary": "",
  "contract_evidence": [
    {{
      "item": "",
      "evidence": "",
      "risk": "none | low | medium | high | unknown"
    }}
  ],
  "party_search_evidence": [
    {{
      "party": "",
      "evidence": "",
      "risk": "none | low | medium | high | unknown",
      "source_urls": []
    }}
  ],
  "risk_points": [],
  "next_actions": []
}}

合同基本信息：
{basic_info_text}

主体搜索结果：
{search_text}

合同线性化文本：
{excerpt}
""".strip()


def _tool_parse_documents(
    file_path: str | None = None,
    attachments_path: str | None = None,
    invoice_path: str | None = None,
    input_path: str | None = None,
    input_directory: str | None = None,
    contract_path: str | None = None,
) -> dict[str, str]:
    """解析合同文件并把结构化结果返回给控制层 AI。"""
    final_file_path = _first_present(file_path, input_path, input_directory, contract_path)
    if not final_file_path:
        return {"ok": False, "output": "missing required argument: file_path"}

    result = parse_documents_to_structured_json(
        file_path=final_file_path,
        attachments_path=attachments_path,
        invoice_path=invoice_path,
    )
    payload = {
        "file_path": final_file_path,
        "attachments_path": attachments_path or "",
        "invoice_path": invoice_path or "",
        "contract_pages": len(result.ocr_payload["contract"]),
        "attachment_pages": len(result.ocr_payload["attachments"]),
        "invoice_pages": len(result.ocr_payload["invoice"]),
        "structured_json": result.structured_json,
    }
    return {"ok": True, "output": json.dumps(payload, ensure_ascii=False, indent=2)}


def _tool_linearize_documents(
    file_path: str | None = None,
    output_dir: str | None = None,
    attachments_path: str | None = None,
    invoice_path: str | None = None,
    input_path: str | None = None,
    input_directory: str | None = None,
    contract_path: str | None = None,
    output_directory: str | None = None,
) -> dict[str, str]:
    """线性化合同文件，并返回输出路径和统计信息。"""
    final_file_path = _first_present(file_path, input_path, input_directory, contract_path)
    if not final_file_path:
        return {"ok": False, "output": "missing required argument: file_path"}

    final_output_dir = _first_present(output_dir, output_directory)
    if not final_output_dir:
        final_output_dir = str(_default_linearized_output_dir(final_file_path))

    result = linearize_documents(
        file_path=final_file_path,
        output_dir=final_output_dir,
        attachments_path=attachments_path,
        invoice_path=invoice_path,
    )
    linearized = result.linearized_document
    payload = {
        "file_path": final_file_path,
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
    file_path: str | None = None,
    output_dir: str | None = None,
    input_path: str | None = None,
    input_file: str | None = None,
    pdf_path: str | None = None,
    output_directory: str | None = None,
) -> dict[str, str]:
    """把单个 PDF 文件转换为图片序列。"""
    final_file_path = _first_present(file_path, input_path, input_file, pdf_path)
    if not final_file_path:
        return {"ok": False, "output": "missing required argument: file_path"}

    final_output_dir = _first_present(output_dir, output_directory)
    if not final_output_dir:
        final_output_dir = str(_default_pdf_output_dir(final_file_path))

    png_paths = pdf2png(pdf_path=final_file_path, output_dir=final_output_dir)
    payload = {
        "file_path": final_file_path,
        "output_dir": str(Path(final_output_dir).resolve()),
        "page_count": len(png_paths),
        "png_paths": png_paths,
    }
    return {"ok": True, "output": json.dumps(payload, ensure_ascii=False, indent=2)}


def _tool_check_contract(
    input_path: str | None = None,
    output_dir: str | None = None,
    attachments_path: str | None = None,
    invoice_path: str | None = None,
    search_enabled: bool = True,
    file_path: str | None = None,
    path: str | None = None,
    input_directory: str | None = None,
    output_directory: str | None = None,
) -> dict[str, str]:
    """一站式合同检查：线性化后核验合同主体真实性和可信风险。"""
    final_input_path = _first_present(input_path, file_path, path, input_directory)
    if not final_input_path:
        return {"ok": False, "output": "missing required argument: input_path"}

    final_output_dir = _first_present(output_dir, output_directory)
    if not final_output_dir:
        final_output_dir = str(_default_linearized_output_dir(final_input_path))

    linearized_result = linearize_documents(
        file_path=final_input_path,
        output_dir=final_output_dir,
        attachments_path=attachments_path,
        invoice_path=invoice_path,
    )
    output_paths = linearized_result.output_paths
    contract_text = str(linearized_result.linearized_document.get("contract_text", ""))
    validity_result = _tool_review_contract_validity(
        linearized_path=output_paths.get("contract"),
        contract_text=contract_text,
        search_enabled=search_enabled,
    )

    payload = {
        "input_path": final_input_path,
        "output_dir": str(Path(final_output_dir).resolve()),
        "contract_pages": len(linearized_result.ocr_payload["contract"]),
        "attachment_pages": len(linearized_result.ocr_payload["attachments"]),
        "invoice_pages": len(linearized_result.ocr_payload["invoice"]),
        "output_paths": output_paths,
        "validity_check": json.loads(validity_result["output"]) if validity_result.get("ok") else validity_result,
    }
    return {"ok": True, "output": json.dumps(payload, ensure_ascii=False, indent=2)}


def _tool_tavliy_search(
    query: str | None = None,
    q: str | None = None,
    sdepth: str = "advanced",
) -> dict[str, str]:
    final_query = _first_present(query, q)
    if not final_query:
        return {"ok": False, "output": "missing required search query"}
    result = tavliy_search(q=final_query, sdepth=sdepth)
    return {
        "ok": True,
        "output": json.dumps(result, ensure_ascii=False, indent=2),
    }


def _tool_review_contract_validity(
    linearized_path: str | None = None,
    contract_text: str | None = None,
    search_enabled: bool = True,
    path: str | None = None,
    file_path: str | None = None,
    input_path: str | None = None,
    text_path: str | None = None,
    linearized_file: str | None = None,
) -> dict[str, str]:
    final_path = _first_present(linearized_path, path, file_path, input_path, text_path, linearized_file)
    loaded_path = ""
    if not contract_text:
        if final_path:
            text_result = sys_readfile(path=final_path, max_chars=80000)
            contract_text = str(text_result.get("content", ""))
            loaded_path = str(text_result.get("path", final_path))
        else:
            latest_path = _find_latest_linearized_contract()
            if latest_path is None:
                return {
                    "ok": False,
                    "output": "missing linearized_path and no contract_linearized.txt found under current working directory",
                }
            text_result = sys_readfile(path=latest_path, max_chars=80000)
            contract_text = str(text_result.get("content", ""))
            loaded_path = str(text_result.get("path", latest_path))

    if not contract_text.strip():
        return {"ok": False, "output": "contract text is empty"}

    basic_info_model = extract_contract_basic_info(contract_text)
    basic_info = _model_to_dict(basic_info_model)

    party_names = []
    for role in ("seller", "buyer"):
        party = basic_info.get(role)
        if isinstance(party, dict):
            name = str(party.get("name", "")).strip()
            if name and name not in party_names:
                party_names.append(name)

    party_searches = [_search_contract_party(name) for name in party_names] if search_enabled else []
    review_prompt = _build_validity_review_prompt(
        contract_text=contract_text,
        basic_info=basic_info,
        party_searches=party_searches,
    )
    review_text = run_message_and_get_reply(
        user_message=review_prompt,
        work_description="你是科技合同有效性风险审核助手，必须基于合同文本和主体搜索证据输出 JSON。",
        max_steps=1,
    )
    try:
        review = parse_json_object(review_text)
    except Exception:
        review = {"raw_review": review_text}

    payload = {
        "linearized_path": loaded_path or final_path or "",
        "basic_info": basic_info,
        "party_searches": party_searches,
        "validity_review": review,
    }
    return {"ok": True, "output": json.dumps(payload, ensure_ascii=False, indent=2)}


def _tool_ls(
    path: str = ".",
    recursive: bool = False,
    max_entries: int = 200,
    include_hidden: bool = True,
    directory: str | None = None,
) -> dict[str, str]:
    final_path = _first_present(path, directory) or "."
    result = sys_ls(
        path=final_path,
        recursive=recursive,
        max_entries=max_entries,
        include_hidden=include_hidden,
    )
    return {"ok": True, "output": json.dumps(result, ensure_ascii=False, indent=2)}


def _tool_readfile(
    path: str | None = None,
    encoding: str = "utf-8",
    max_chars: int = 20000,
    file_path: str | None = None,
) -> dict[str, str]:
    final_path = _first_present(path, file_path)
    if not final_path:
        return {"ok": False, "output": "missing required argument: path"}
    result = sys_readfile(path=final_path, encoding=encoding, max_chars=max_chars)
    return {"ok": True, "output": json.dumps(result, ensure_ascii=False, indent=2)}


def _tool_readimage(
    path: str | None = None,
    max_bytes: int = 6_000_000,
    include_data_url: bool = True,
    file_path: str | None = None,
    input_path: str | None = None,
    image_path: str | None = None,
) -> dict[str, str]:
    final_path = _first_present(path, file_path, input_path, image_path)
    if not final_path:
        return {"ok": False, "output": "missing required argument: path"}
    result = sys_readimage(
        path=final_path,
        max_bytes=max_bytes,
        include_data_url=include_data_url,
    )
    image_url = str(result.get("data_url") or "")
    summary = {
        "path": result.get("path", ""),
        "name": result.get("name", ""),
        "mime_type": result.get("mime_type", ""),
        "size": result.get("size", 0),
        "image_url_attached": bool(image_url),
        "note": "Image bytes are attached to the next model call as image_url, not printed inline.",
    }
    return {
        "ok": True,
        "output": json.dumps(summary, ensure_ascii=False, indent=2),
        "image_url": image_url,
        "image_name": result.get("name", ""),
        "image_path": result.get("path", ""),
        "image_mime_type": result.get("mime_type", ""),
    }


def _tool_writefile(
    path: str | None = None,
    content: str = "",
    encoding: str = "utf-8",
    overwrite: bool = False,
    create_parents: bool = True,
    file_path: str | None = None,
) -> dict[str, str]:
    final_path = _first_present(path, file_path)
    if not final_path:
        return {"ok": False, "output": "missing required argument: path"}
    result = sys_writefile(
        path=final_path,
        content=content,
        encoding=encoding,
        overwrite=overwrite,
        create_parents=create_parents,
    )
    return {"ok": True, "output": json.dumps(result, ensure_ascii=False, indent=2)}


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
        "check_contract": _tool_check_contract,
        "tavliy_search": _tool_tavliy_search,
        "review_contract_validity": _tool_review_contract_validity,
        "ls": _tool_ls,
        "readfile": _tool_readfile,
        "readimage": _tool_readimage,
        "writefile": _tool_writefile,
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
