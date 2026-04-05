from __future__ import annotations

import argparse
import json
import sys

from core.application.documents import parse_documents_to_structured_json
from core.infrastructure.ai.logger import get_logger
from core.shared.path_utils import ensure_parent_dir

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

def handle_parse_command(args: argparse.Namespace) -> int:
    """执行 parse 子命令并输出结构化 JSON。"""
    result = parse_documents_to_structured_json(
        file_path=args.file,
        attachments_path=args.attachments,
        invoice_path=args.invoice,
    )
    json_text = json.dumps(result.structured_json, ensure_ascii=False, indent=2)
    print(json_text)

    if args.output:
        output_path = ensure_parent_dir(args.output)
        output_path.write_text(json_text, encoding="utf-8")
        print(f"\nSaved output to: {output_path}", file=sys.stderr)

    return 0
