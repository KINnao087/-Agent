from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain.tools import ToolRuntime
from langgraph.types import Command

from core.application.contracts import (
    check_contract_seals_service,
    review_contract_validity,
)
from core.application.contracts.cross_page_seal_services import check_cpseal_services
from core.application.documents import linearize_documents, parse_documents_to_structured_json
from core.infrastructure.RAG import format_chunks, get_and_rerank_chunks
from core.infrastructure.basetools.sys_cmds import ls as sys_ls
from core.infrastructure.basetools.sys_cmds import readfile as sys_readfile
from core.infrastructure.basetools.sys_cmds import readimage as sys_readimage
from core.infrastructure.basetools.sys_cmds import writefile as sys_writefile
from core.infrastructure.text import pdf2png
from core.infrastructure.web_searcher.searcher import tavily_search


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _default_output_dir(input_path: str, suffix: str) -> str:
    path = Path(input_path)
    parent = path if path.is_dir() else path.parent
    return str((parent / suffix).resolve())


@tool
def pdf2pngs(file_path: str, output_dir: str = "") -> str:
    """将单个 PDF 文件转换为 PNG 图片列表。"""
    target_dir = output_dir or _default_output_dir(file_path, f"{Path(file_path).stem}_pdf_pages")
    paths = pdf2png(file_path, target_dir)
    return _json({"output_dir": target_dir, "page_count": len(paths), "png_paths": paths})


@tool
def parse_documents(
    file_path: str,
    attachments_path: str = "",
    invoice_path: str = "",
) -> str:
    """将 PDF、PNG、JPG 或图片目录中的合同、附件和发票解析为结构化 JSON。"""
    result = parse_documents_to_structured_json(
        file_path=file_path,
        attachments_path=attachments_path or None,
        invoice_path=invoice_path or None,
    )
    return _json(
        {
            "contract_pages": len(result.ocr_payload["contract"]),
            "attachment_pages": len(result.ocr_payload["attachments"]),
            "invoice_pages": len(result.ocr_payload["invoice"]),
            "structured_json": result.structured_json,
        }
    )


@tool
def linearize_contract_documents(
    file_path: str,
    output_dir: str = "",
    attachments_path: str = "",
    invoice_path: str = "",
) -> str:
    """将 PDF、PNG、JPG 或图片目录中的文档 OCR 线性化并写入文本文件。"""
    target_dir = output_dir or _default_output_dir(file_path, "linearized_output")
    result = linearize_documents(
        file_path=file_path,
        output_dir=target_dir,
        attachments_path=attachments_path or None,
        invoice_path=invoice_path or None,
    )
    return _json(
        {
            "output_dir": target_dir,
            "contract_pages": len(result.ocr_payload["contract"]),
            "attachment_pages": len(result.ocr_payload["attachments"]),
            "invoice_pages": len(result.ocr_payload["invoice"]),
            "output_paths": result.output_paths,
        }
    )


@tool
def review_contract(
    input_path: str,
    output_dir: str = "",
    search_enabled: bool = True,
) -> str:
    """执行合同主体真实性和有效性风险初审，不包含完整性或签章审核。"""
    target_dir = output_dir or _default_output_dir(input_path, "linearized_output")
    documents = linearize_documents(file_path=input_path, output_dir=target_dir)
    validity = review_contract_validity(
        linearized_path=documents.output_paths["contract"],
        search_enabled=search_enabled,
    )
    return _json(
        {
            "scope": [
                "ocr_linearization",
                "contract_party_extraction",
                "public_info_search",
                "validity_risk_precheck",
            ],
            "output_paths": documents.output_paths,
            "validity": validity,
        }
    )


@tool
def review_validity(
    linearized_path: str,
    search_enabled: bool = True,
) -> str:
    """根据线性化合同文本审核主体公开信息和合同有效性风险。"""
    return _json(
        review_contract_validity(
            linearized_path=linearized_path,
            search_enabled=search_enabled,
        )
    )


@tool
def check_contract_seals(input_path: str) -> str:
    """审核合同图片目录中的普通红色签章。"""
    return check_contract_seals_service(input_path)["output"]


@tool
def check_cross_page_seal(input_path: str) -> str:
    """审核 PDF、图片或图片目录中的骑缝章。"""
    return _json(asdict(check_cpseal_services(input_path)))


@tool
def web_search(query: str, search_depth: str = "advanced") -> str:
    """搜索公开网页信息。"""
    return _json(tavily_search(q=query, sdepth=search_depth))


@tool
def search_contract_rules(query: str) -> str:
    """从本地合同审核规则知识库检索相关规则。"""
    return format_chunks(get_and_rerank_chunks(query))


@tool
def list_files(
    path: str = ".",
    recursive: bool = False,
    max_entries: int = 200,
) -> str:
    """列出本机目录中的文件和子目录。"""
    return _json(sys_ls(path=path, recursive=recursive, max_entries=max_entries))


@tool
def read_text_file(path: str, max_chars: int = 20000) -> str:
    """读取本机 UTF-8 文本文件。"""
    return _json(sys_readfile(path=path, max_chars=max_chars))


@tool
def read_image(path: str, runtime: ToolRuntime) -> Command:
    """读取本机图片并将图片附加到下一轮模型输入。"""
    result = sys_readimage(path=path, include_data_url=True)
    summary = _json(
        {
            "path": result["path"],
            "name": result["name"],
            "mime_type": result["mime_type"],
            "size": result["size"],
        }
    )
    return Command(
        update={
            "messages": [
                ToolMessage(content=summary, tool_call_id=runtime.tool_call_id),
                HumanMessage(
                    content=[
                        {"type": "text", "text": f"图片文件：{result['path']}"},
                        {
                            "type": "image_url",
                            "image_url": {"url": result["data_url"]},
                        },
                    ]
                ),
            ]
        }
    )


@tool
def write_text_file(
    path: str,
    content: str,
    overwrite: bool = False,
) -> str:
    """向本机路径写入 UTF-8 文本。"""
    return _json(
        sys_writefile(
            path=path,
            content=content,
            overwrite=overwrite,
            create_parents=True,
        )
    )


TOOLS = [
    pdf2pngs,
    parse_documents,
    linearize_contract_documents,
    review_contract,
    review_validity,
    check_contract_seals,
    check_cross_page_seal,
    web_search,
    search_contract_rules,
    list_files,
    read_text_file,
    read_image,
    write_text_file,
]
