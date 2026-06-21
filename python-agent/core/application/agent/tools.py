from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command

from core.application.reviews import get_contract_review_service
from core.infrastructure.basetools.sys_cmds import ls as sys_ls
from core.infrastructure.basetools.sys_cmds import readfile as sys_readfile
from core.infrastructure.basetools.sys_cmds import readimage as sys_readimage
from core.infrastructure.basetools.sys_cmds import writefile as sys_writefile
from core.shared.logging import get_logger

_logger = get_logger("tools")


def _allowed_tool_roots() -> list[str]:
    py_root = Path(__file__).parent.parent.parent.parent
    project_root = py_root.parent
    roots = [
        (py_root / "artifacts").resolve(),
        (py_root / "data").resolve(),
    ]

    optional_roots = [
        project_root / "java-backend" / "uploads",
        project_root / "uploads",
        project_root / "test" / "testfiles",
        py_root / "test" / "testfiles",
        Path("/app/uploads"),
    ]
    for candidate in optional_roots:
        if candidate.is_dir():
            roots.append(candidate.resolve())

    return [str(root) for root in roots]


def _ensure_allowed_path(path: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    allowed_roots = _allowed_tool_roots()
    if not any(str(resolved).startswith(root) for root in allowed_roots):
        raise PermissionError(
            f"无权访问路径: {resolved}。仅允许访问 artifacts、data、uploads、testfiles 目录。"
        )
    return resolved


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except (TypeError, ValueError) as exc:
        _logger.error("JSON serialization failed")
        return json.dumps(
            {
                "error": True,
                "error_type": type(exc).__name__,
                "message": f"结果序列化失败: {exc}",
            },
            ensure_ascii=False,
            indent=2,
        )


def _safe_json(fn, *args, **kwargs) -> str:
    try:
        return _json(fn(*args, **kwargs))
    except Exception as exc:
        _logger.error("Tool call failed: {}", getattr(fn, "__name__", repr(fn)))
        return _json(
            {
                "error": True,
                "error_type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )


def _permission_error(path: str, exc: PermissionError) -> str:
    return _json(
        {
            "error": True,
            "error_type": "PermissionError",
            "message": str(exc),
            "path": str(Path(path).expanduser().resolve()),
        }
    )


@tool
def find_contract_review(
    contract_path: str,
    attachments_path: str = "",
    invoice_path: str = "",
    platform_basic_info: dict[str, Any] | None = None,
) -> str:
    """按材料内容指纹查询已有合同审核任务，不调用审核模型。"""
    return _safe_json(
        get_contract_review_service().find_contract_review,
        contract_path=contract_path,
        attachments_path=attachments_path,
        invoice_path=invoice_path,
        platform_basic_info=platform_basic_info,
    )


@tool
def prepare_contract(
    contract_path: str,
    attachments_path: str = "",
    invoice_path: str = "",
    platform_basic_info: dict[str, Any] | None = None,
) -> str:
    """创建或恢复审核任务，完成材料标准化、OCR 和线性化，返回 review_id。"""
    return _safe_json(
        get_contract_review_service().prepare_contract,
        contract_path=contract_path,
        attachments_path=attachments_path,
        invoice_path=invoice_path,
        platform_basic_info=platform_basic_info,
    )


@tool
def check_basic_info(review_id: str) -> str:
    """提取合同基本信息，并在存在平台数据时执行字段核对。"""
    return _safe_json(get_contract_review_service().check_basic_info, review_id)


@tool
def check_text_integrity(review_id: str) -> str:
    """审核合同页面连续性、文本完整性、替换页风险和清晰度。"""
    return _safe_json(get_contract_review_service().check_text_integrity, review_id)


@tool
def check_contract_seals(review_id: str) -> str:
    """审核甲乙方普通签章，不包含骑缝章。"""
    return _safe_json(get_contract_review_service().check_contract_seals, review_id)


@tool
def check_cross_page_seal(review_id: str) -> str:
    """审核骑缝章存在性、连续性、缺失页和风险等级。"""
    return _safe_json(get_contract_review_service().check_cross_page_seal, review_id)


@tool
def check_contract_authenticity(
    review_id: str,
    search_enabled: bool = True,
) -> str:
    """结合合同主体、公开信息和合同文本审核真实性与有效性风险。"""
    return _safe_json(
        get_contract_review_service().check_contract_authenticity,
        review_id,
        search_enabled=search_enabled,
    )


@tool
def get_review_status(review_id: str) -> str:
    """查询审核任务进度、失败项和因版本变化而失效的专项。"""
    return _safe_json(get_contract_review_service().get_review_status, review_id)


@tool
def write_review_report(review_id: str) -> str:
    """从已持久化专项结果确定性生成 JSON 和 Markdown 综合报告。"""
    return _safe_json(get_contract_review_service().write_review_report, review_id)


@tool
def get_review_result(review_id: str, step_name: str = "") -> str:
    """直接读取已有专项结果或全部结果，不重新执行审核。"""
    return _safe_json(
        get_contract_review_service().get_review_result,
        review_id,
        step_name,
    )


@tool
def list_files(
    path: str = ".",
    recursive: bool = False,
    max_entries: int = 200,
) -> str:
    """列出指定目录中的文件和子目录，仅允许访问审核产物、上传目录和测试样例目录。"""
    try:
        resolved = _ensure_allowed_path(path)
    except PermissionError as exc:
        return _permission_error(path, exc)
    return _safe_json(
        sys_ls,
        path=str(resolved),
        recursive=recursive,
        max_entries=max_entries,
    )


@tool
def read_text_file(path: str, max_chars: int = 20000) -> str:
    """读取本机 UTF-8 文本文件。"""
    try:
        resolved = _ensure_allowed_path(path)
    except PermissionError as exc:
        return _permission_error(path, exc)
    return _safe_json(sys_readfile, path=str(resolved), max_chars=max_chars)


@tool
def read_image(path: str, runtime: ToolRuntime) -> Command:
    """读取本机图片并将图片附加到下一轮模型输入。"""
    try:
        resolved = _ensure_allowed_path(path)
        result = sys_readimage(path=str(resolved), include_data_url=True)
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
                            {"type": "text", "text": f"图片文件: {result['path']}"},
                            {
                                "type": "image_url",
                                "image_url": {"url": result["data_url"]},
                            },
                        ]
                    ),
                ]
            }
        )
    except Exception as exc:
        _logger.error("read_image failed")
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=_json(
                            {
                                "error": True,
                                "error_type": type(exc).__name__,
                                "message": f"读取图片失败: {exc}",
                            }
                        ),
                        tool_call_id=runtime.tool_call_id,
                    )
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
    return _safe_json(
        sys_writefile,
        path=path,
        content=content,
        overwrite=overwrite,
        create_parents=True,
    )


TOOLS = [
    find_contract_review,
    prepare_contract,
    check_basic_info,
    check_text_integrity,
    check_contract_seals,
    check_cross_page_seal,
    check_contract_authenticity,
    get_review_status,
    write_review_report,
    get_review_result,
    list_files,
    read_text_file,
    read_image,
    write_text_file,
]
