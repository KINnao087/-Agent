# 命令行入口

from __future__ import annotations

import argparse
import sys

from .cli_shell import add_shell_command, handle_shell_command
from .linearizer import add_linearizer_command, handle_linearizer_command
from .parse import add_parse_command, handle_parse_command


def build_parser() -> argparse.ArgumentParser:
    """构建整个程序的命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description="科技合同审核 CLI。无参数时默认进入交互式 shell。",
    )
    subparsers = parser.add_subparsers(dest="command")
    add_shell_command(subparsers)
    add_parse_command(subparsers)
    add_linearizer_command(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    """命令行主入口：解析参数并分发到对应处理函数。"""
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if not raw_argv:
        # 模仿 codex/claude code 的交互习惯：无参数直接进入 shell。
        return handle_shell_command()

    parser = build_parser()
    args = parser.parse_args(raw_argv)

    try:
        if args.command == "shell":
            return handle_shell_command(args)
        if args.command == "parse":
            return handle_parse_command(args)
        if args.command == "linearizer":
            return handle_linearizer_command(args)

        parser.print_help()
        return 1
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
