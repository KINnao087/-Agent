from __future__ import annotations

import argparse
import json
import sys

from core.ai import structure_ocr_json
from core.ai.logger import get_logger
from core.path_utils import ensure_parent_dir, resolve_path
from core.text import build_linearized_document, parse_path_to_json_list

logger = get_logger("parse-command")


def add_parse_command(subparsers: argparse._SubParsersAction) -> None:
    """注册 parse 子命令及其参数。"""
    parse_parser = subparsers.add_parser(
        "parse",
        help="读取 PNG，先做 OCR，再输出 AI 整理后的结构化 JSON。",
    )
    parse_parser.add_argument(
        "--file",
        "-f",
        required=True,
        help="待解析的主文档 PNG 文件或目录路径。",
    )
    parse_parser.add_argument(
        "--output",
        "-o",
        help="可选，指定结构化 JSON 的输出路径。",
    )
    parse_parser.add_argument(
        "--attachments",
        "-a",
        help="可选，附件 PNG 文件或目录路径。",
    )
    parse_parser.add_argument(
        "--invoice",
        "-invoice",
        "-i",
        dest="invoice",
        help="可选，发票 PNG 文件或目录路径。",
    )


def _load_attachment_ocr_list(attachments_path: str | None) -> list[dict]:
    """调用 text 层公开接口，读取附件 OCR JSON 列表。"""
    attachment_list = parse_path_to_json_list(attachments_path)
    logger.info("Loaded {} attachment OCR json item(s)", len(attachment_list))
    return attachment_list


def _load_invoice_ocr_list(invoice_path: str | None) -> list[dict]:
    """调用 text 层公开接口，读取发票 OCR JSON 列表。"""
    invoice_list = parse_path_to_json_list(invoice_path)
    logger.info("Loaded {} invoice OCR json item(s)", len(invoice_list))
    return invoice_list


def struct_json(ocr_payload: dict) -> dict:
    """调用 AI 包公开接口，将 OCR JSON 载荷转成结构化 JSON。"""
    logger.info("OCR payload prepared")
    return structure_ocr_json(ocr_payload)


def handle_parse_command(args: argparse.Namespace) -> int:
    """执行 parse 子命令并输出结构化 JSON。"""
    ocr_payload = {
        "input_path": str(resolve_path(args.file)),
        "contract": parse_path_to_json_list(args.file),
        "attachments": _load_attachment_ocr_list(args.attachments),
        "invoice": _load_invoice_ocr_list(args.invoice),
    }
    ocr_payload["linearized"] = build_linearized_document(ocr_payload)

    logger.info(
        "Start structuring contract_pages={}, attachments={}, invoice_pages={}, linearized_chars={}",
        len(ocr_payload["contract"]),
        len(ocr_payload["attachments"]),
        len(ocr_payload["invoice"]),
        len(ocr_payload["linearized"]["full_text"]),
    )

    structured_json = struct_json(ocr_payload)
    json_text = json.dumps(structured_json, ensure_ascii=False, indent=2)
    print(json_text)

    if args.output:
        output_path = ensure_parent_dir(args.output)
        output_path.write_text(json_text, encoding="utf-8")
        print(f"\nSaved output to: {output_path}", file=sys.stderr)

    return 0
