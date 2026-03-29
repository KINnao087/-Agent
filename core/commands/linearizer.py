from __future__ import annotations

import argparse

from core.ai.logger import get_logger
from core.path_utils import resolve_path
from core.text import build_linearized_document, parse_path_to_json_list, write_linearized_outputs

logger = get_logger("linearizer-command")


def add_linearizer_command(subparsers: argparse._SubParsersAction) -> None:
    """注册 linearizer 子命令及其参数。"""
    linearizer_parser = subparsers.add_parser(
        "linearizer",
        help="读取 PNG，执行 OCR 线性化，并输出合同/附件/发票文本文件。",
    )
    linearizer_parser.add_argument(
        "--file",
        "-f",
        required=True,
        help="待线性化的主文档 PNG 文件或目录路径。",
    )
    linearizer_parser.add_argument(
        "--output-dir",
        "-o",
        default="linearized_output",
        help="可选，线性化文本输出目录，默认写入 ./linearized_output。",
    )
    linearizer_parser.add_argument(
        "--attachments",
        "-a",
        help="可选，附件 PNG 文件或目录路径。",
    )
    linearizer_parser.add_argument(
        "--invoice",
        "-invoice",
        "-i",
        dest="invoice",
        help="可选，发票 PNG 文件或目录路径。",
    )


def handle_linearizer_command(args: argparse.Namespace) -> int:
    """执行 linearizer 子命令并输出线性化文本文件。"""
    ocr_payload = {
        "input_path": str(resolve_path(args.file)),
        "contract": parse_path_to_json_list(args.file),
        "attachments": parse_path_to_json_list(args.attachments),
        "invoice": parse_path_to_json_list(args.invoice),
    }
    linearized = build_linearized_document(ocr_payload)
    output_paths = write_linearized_outputs(linearized, args.output_dir)

    logger.info(
        "Linearized contract_pages={}, attachments={}, invoice_pages={}, output_dir={}",
        len(ocr_payload["contract"]),
        len(ocr_payload["attachments"]),
        len(ocr_payload["invoice"]),
        resolve_path(args.output_dir),
    )

    print(f"contract_pages={len(ocr_payload['contract'])}")
    print(f"attachment_pages={len(ocr_payload['attachments'])}")
    print(f"invoice_pages={len(ocr_payload['invoice'])}")
    print(f"contract_text_chars={len(linearized['contract_text'])}")
    print(f"attachments_text_chars={len(linearized['attachment_text'])}")
    print(f"invoice_text_chars={len(linearized['invoice_text'])}")
    print(f"contract_linearized={output_paths['contract']}")
    print(f"attachments_linearized={output_paths['attachments']}")
    print(f"invoice_linearized={output_paths['invoice']}")
    return 0
