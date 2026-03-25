#command line interface

from __future__ import annotations

import argparse
import sys

from .parse import add_parse_command, handle_parse_command


def build_parser() -> argparse.ArgumentParser:
    """构建整个程序的命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description="文档文本结构化解析工具。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_parse_command(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    """命令行主入口：解析参数并分发到对应处理函数。"""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "parse":
            return handle_parse_command(args)

        parser.print_help()
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
