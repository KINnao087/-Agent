from __future__ import annotations

import asyncio
from pathlib import Path

from core.application.agent.chat_service import TraceEvent
from core.presentation.cli.cli_shell import (
    ContractCliShell,
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


class FakeChatService:
    def stream(self, message: str):
        yield TraceEvent(
            kind="turn_start",
            summary="开始处理用户请求",
            detail=message,
        )
        yield TraceEvent(
            kind="tool_start",
            summary="调用 list_files",
            detail='{"path": "."}',
            tool_call_id="call-1",
            tool_name="list_files",
        )
        yield TraceEvent(
            kind="tool_result",
            summary='{"entry_count": 1}',
            detail='{"entry_count": 1}',
            tool_call_id="call-1",
            tool_name="list_files",
            elapsed_ms=12,
        )
        yield TraceEvent(
            kind="final",
            summary="完成",
            detail="完成",
        )


def test_trace_tree_can_render_toggle_and_clear() -> None:
    async def exercise() -> None:
        app = ContractCliShell(chat_service=FakeChatService())
        async with app.run_test() as pilot:
            app._append_trace_event(
                TraceEvent(
                    kind="turn_start",
                    summary="开始处理用户请求",
                    detail="列出文件",
                )
            )
            app._append_trace_event(
                TraceEvent(
                    kind="tool_start",
                    summary="调用 list_files",
                    detail='{"path": "."}',
                    tool_call_id="call-1",
                    tool_name="list_files",
                )
            )
            app._append_trace_event(
                TraceEvent(
                    kind="tool_result",
                    summary='{"entry_count": 1}',
                    detail='{"entry_count": 1}',
                    tool_call_id="call-1",
                    tool_name="list_files",
                    elapsed_ms=12,
                )
            )

            tree = app.query_one("#trace-tree")
            assert len(tree.root.children) == 1
            tool_node = tree.root.children[0].children[1]
            assert "完成: list_files" in str(tool_node.label)
            assert tool_node.is_expanded is False

            await pilot.press("ctrl+t")
            assert tree.display is False
            await pilot.press("ctrl+t")
            assert tree.display is True

            await pilot.press("ctrl+l")
            assert len(tree.root.children) == 0

    asyncio.run(exercise())
