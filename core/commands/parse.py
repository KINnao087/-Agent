from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.ai import structure_ocr_json
from core.text import parse_file_to_json

from core.ai.logger import get_logger

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
        help="待解析的 PNG 文件路径。",
    )
    parse_parser.add_argument(
        "--output",
        "-o",
        help="可选，指定结构化 JSON 的输出路径。",
    )


def _extract_json_text(response_text: str) -> str:
    """从模型回复中提取 JSON 文本。"""
    text = (response_text or "").strip()
    if not text:
        raise ValueError("model returned empty content")

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    if text.startswith("{") and text.endswith("}"):
        return text

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    raise ValueError("model response does not contain a JSON object")


def _parse_model_json(response_text: str) -> dict:
    """把模型回复解析成 JSON 对象。"""
    data = json.loads(_extract_json_text(response_text))
    if not isinstance(data, dict):
        raise ValueError("model response JSON must be an object")
    return data


def struct_json(ocr_json: dict) -> dict:
    logger.info("ocr_json" + json.dumps(ocr_json, ensure_ascii=False))
    """调用 AI 包的公开接口，将 OCR JSON 转成结构化 JSON。"""
    reply_text = structure_ocr_json(ocr_json)
    return _parse_model_json(reply_text)


def handle_parse_command(args: argparse.Namespace) -> int:
    """执行 parse 子命令并输出结构化 JSON。"""
    ocr_json = parse_file_to_json(args.file)
    structured_json = struct_json(ocr_json)
    json_text = json.dumps(structured_json, ensure_ascii=False, indent=2)
    print(json_text)

    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = Path.cwd() / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_text, encoding="utf-8")
        print(f"\nSaved output to: {output_path}", file=sys.stderr)

    return 0
