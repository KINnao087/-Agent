from __future__ import annotations

import core.commands.cli as cli_module


def test_build_parser_registers_linearizer_command() -> None:
    """CLI 应注册 linearizer 子命令。"""
    parser = cli_module.build_parser()

    args = parser.parse_args(["linearizer", "--file", "demo"])

    assert args.command == "linearizer"
    assert args.file == "demo"
    assert args.output_dir == "linearized_output"


def test_main_dispatches_to_linearizer_handler(monkeypatch) -> None:
    """main 应把 linearizer 命令分发到对应 handler。"""
    called: list[str] = []

    def fake_handle_linearizer_command(args) -> int:
        called.append(args.command)
        return 0

    monkeypatch.setattr(cli_module, "handle_linearizer_command", fake_handle_linearizer_command)

    result = cli_module.main(["linearizer", "--file", "demo"])

    assert result == 0
    assert called == ["linearizer"]
