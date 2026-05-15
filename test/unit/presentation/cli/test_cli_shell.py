from __future__ import annotations

from pathlib import Path

from core.presentation.cli.cli_shell import (
    expand_input_path_aliases,
    format_paths_for_display,
    normalize_paste_for_input,
    prepare_cli_message,
    prepare_paste_for_input,
)


def test_prepare_cli_message_displays_full_path_in_chat_history() -> None:
    message = prepare_cli_message("parse D:/contracts/contract.pdf")
    expected_path = str(Path("D:/contracts/contract.pdf").resolve(strict=False))

    assert message.agent_text == f'parse "{expected_path}"'
    assert message.display_text == f'parse "{expected_path}"'
    assert "[contract.pdf]" not in message.display_text


def test_normalize_paste_for_input_displays_short_alias() -> None:
    assert normalize_paste_for_input("parse D:/contracts/contract.pdf") == "parse [contract.pdf]"


def test_pasted_alias_expands_to_full_path_before_submit() -> None:
    prepared = prepare_paste_for_input("parse D:/contracts/contract.pdf")
    expected_path = str(Path("D:/contracts/contract.pdf").resolve(strict=False))

    assert prepared.input_text == "parse [contract.pdf]"
    assert expand_input_path_aliases(prepared.input_text, prepared.aliases) == f'parse "{expected_path}"'


def test_format_paths_for_display_keeps_full_path() -> None:
    expected_path = str(Path("D:/contracts/result.txt").resolve(strict=False))

    assert format_paths_for_display("output D:/contracts/result.txt") == f'output "{expected_path}"'
