from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any
from urllib.parse import unquote, urlparse

from core.application.agent.chat_service import (
    CliChatService,
    TraceEvent,
    create_cli_chat_service,
)
from core.shared.logging import get_latest_log_path, get_logger, start_live_log_terminal

TEXTUAL_INSTALL_HINT = (
    "未安装 Textual。请先执行: .\\.venv\\Scripts\\python.exe -m pip install textual"
)


def add_shell_command(subparsers: argparse._SubParsersAction) -> None:
    """注册交互式 shell 子命令。"""
    subparsers.add_parser(
        "shell",
        help="启动 Textual 交互式对话 shell。",
    )


def handle_shell_command(args: argparse.Namespace | None = None) -> int:
    """执行 shell 子命令。"""
    del args
    try:
        return run_cli_shell()
    except KeyboardInterrupt:
        return 0

# 当前 shell 依赖 Textual，因此在模块加载阶段直接导入 UI 组件。
from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Input, RichLog, Static, Tree
from textual.widgets.tree import TreeNode
from rich.text import Text

logger = get_logger("cli_shell")


_PATH_TOKEN_RE = re.compile(
    r"""
    (?P<quoted>
        (?P<quote>["'])
        (?P<quoted_path>
            (?:file:///.*?)
            |
            (?:[A-Za-z]:[\\/].*?)
            |
            (?:\\\\.*?)
        )
        (?P=quote)
    )
    |
    (?P<bare>
        file:///[^\s"'<>|]+
        |
        [A-Za-z]:[\\/][^\s"'<>|，；。]+
        |
        \\\\[^\s"'<>|，；。]+
    )
    """,
    re.VERBOSE,
)


@dataclass(frozen=True, slots=True)
class PreparedCliMessage:
    """CLI 输入在内部执行和界面展示时使用的两种形态。"""

    agent_text: str
    display_text: str


@dataclass(frozen=True, slots=True)
class PreparedInputPaste:
    """粘贴到输入框时使用的短文本，以及提交时还原路径所需的映射。"""

    input_text: str
    aliases: dict[str, str]


def _clean_dragged_path(raw_path: str) -> str:
    """把终端拖拽或粘贴进来的路径文本清理成普通文件系统路径。"""
    text = raw_path.strip().strip('"\'')
    if text.lower().startswith("file://"):
        parsed = urlparse(text)
        path = unquote(parsed.path)
        if parsed.netloc:
            return f"//{parsed.netloc}{path}"
        if re.match(r"^/[A-Za-z]:/", path):
            return path[1:]
        return path
    return text


def _absolute_path_text(path_text: str) -> str:
    """把输入路径转换为绝对路径字符串，不要求路径当前一定存在。"""
    cleaned = _clean_dragged_path(path_text)
    return str(Path(cleaned).expanduser().resolve(strict=False))


def _file_display_name(path_text: str) -> str:
    """返回路径用于输入框展示的短名称。"""
    cleaned = _clean_dragged_path(path_text)
    if re.match(r"^(?:[A-Za-z]:[\\/]|\\\\)", cleaned):
        name = PureWindowsPath(cleaned).name
    else:
        name = Path(cleaned).name
    return name or cleaned


def prepare_cli_message(raw_message: str) -> PreparedCliMessage:
    """把用户输入中的文件路径转成绝对路径，同时生成聊天窗口展示文本。"""
    normalized_parts: list[str] = []
    display_parts: list[str] = []
    cursor = 0

    for match in _PATH_TOKEN_RE.finditer(raw_message):
        start, end = match.span()
        path_text = match.group("quoted_path") or match.group("bare") or ""
        if not path_text:
            continue

        normalized_parts.append(raw_message[cursor:start])
        display_parts.append(raw_message[cursor:start])

        absolute_path = _absolute_path_text(path_text)
        normalized_path = f'"{absolute_path}"'
        normalized_parts.append(normalized_path)
        display_parts.append(normalized_path)
        cursor = end

    normalized_parts.append(raw_message[cursor:])
    display_parts.append(raw_message[cursor:])
    return PreparedCliMessage(
        agent_text="".join(normalized_parts).strip(),
        display_text="".join(display_parts).strip(),
    )


def format_paths_for_display(text: str) -> str:
    """把任意文本里的路径规范化成完整路径，用于聊天窗口展示。"""
    return prepare_cli_message(text).display_text


def prepare_paste_for_input(text: str) -> PreparedInputPaste:
    """把粘贴文本里的路径压缩成输入框短别名，并记录别名对应的完整路径。"""
    compact_text = " ".join((text or "").splitlines()).strip()
    if not compact_text:
        return PreparedInputPaste(input_text="", aliases={})

    input_parts: list[str] = []
    aliases: dict[str, str] = {}
    cursor = 0

    for match in _PATH_TOKEN_RE.finditer(compact_text):
        start, end = match.span()
        path_text = match.group("quoted_path") or match.group("bare") or ""
        if not path_text:
            continue

        input_parts.append(compact_text[cursor:start])

        alias = f"[{_file_display_name(path_text)}]"
        normalized_path = f'"{_absolute_path_text(path_text)}"'
        input_parts.append(alias)
        aliases[alias] = normalized_path
        cursor = end

    input_parts.append(compact_text[cursor:])
    return PreparedInputPaste(input_text="".join(input_parts), aliases=aliases)


def expand_input_path_aliases(text: str, aliases: dict[str, str]) -> str:
    """提交输入框内容前，把 [文件名] 短别名还原成完整路径。"""
    expanded = text
    for alias, path in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        expanded = expanded.replace(alias, path)
    return expanded


def normalize_paste_for_input(text: str) -> str:
    """把粘贴或终端拖入的路径文本转换成适合单行输入框的文本。"""
    return prepare_paste_for_input(text).input_text


class PathInput(Input):
    """支持把终端粘贴进来的文件路径规范化成绝对路径。"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.path_aliases: dict[str, str] = {}

    def on_paste(self, event: events.Paste) -> None:
        prepared_paste = prepare_paste_for_input(event.text)
        if not prepared_paste.input_text:
            event.prevent_default()
            event.stop()
            return

        self.path_aliases.update(prepared_paste.aliases)
        self.insert_text_at_cursor(prepared_paste.input_text)
        event.prevent_default()
        event.stop()

    def expand_path_aliases(self, text: str) -> str:
        return expand_input_path_aliases(text, self.path_aliases)

    def clear_path_aliases(self) -> None:
        self.path_aliases.clear()


class ContractCliShell(App[None]):
    TITLE = "Contract Agent Shell"
    live_log_terminal_started = False
    # SUB_TITLE = "无参数默认进入的 CLI 对话模式"
    CSS = """
    Screen {
        layout: vertical;
    }

    #chat-log {
        height: 2fr;
        border: solid $accent;
        padding: 1 2;
    }

    #trace-tree {
        height: 1fr;
        border: solid $secondary;
        padding: 0 1;
    }

    #status {
        height: 3;
        border: round $secondary;
        padding: 0 1;
    }

    #prompt {
        margin: 1 0 0 0;
    }
    """
    BINDINGS = [
        Binding("ctrl+c", "quit", "退出"),
        Binding("ctrl+l", "clear_chat", "清屏"),
        Binding("ctrl+t", "toggle_trace", "执行轨迹"),
    ]

    def __init__(
        self,
        *args: Any,
        chat_service: CliChatService | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        # chat_service 在 shell 生命周期内复用，保存多轮对话上下文。
        self.chat_service = chat_service or create_cli_chat_service()
        self._trace_turn = 0
        self._trace_turn_node: TreeNode[None] | None = None
        self._trace_tool_nodes: dict[str, TreeNode[None]] = {}

    def compose(self) -> ComposeResult:
        # 聊天记录与执行轨迹分离，避免调试数据淹没最终回答。
        yield Header(show_clock=True)
        yield RichLog(id="chat-log", wrap=True, markup=False, highlight=False)
        yield Tree("Agent 执行轨迹", id="trace-tree")
        yield Static("状态: 空闲", id="status")
        yield PathInput(
            placeholder="输入问题，或直接描述要处理的合同文件路径和需求...",
            id="prompt",
        )
        yield Footer()

    def on_mount(self) -> None:
        trace_tree = self.query_one("#trace-tree", Tree)
        trace_tree.root.expand()
        self._append_system(
            "已进入交互模式。Ctrl+T 显隐执行轨迹，Ctrl+L 清屏，Ctrl+C 退出。"
        )
        self._append_system(
            "例如：请解析 D:/contracts/demo 目录下的合同，并输出结构化 JSON。"
        )
        self._append_system(f"日志文件: {get_latest_log_path()}")
        if self.live_log_terminal_started:
            self._append_system("已打开实时日志窗口。")
        else:
            self._append_system("未自动打开实时日志窗口，可直接查看 latest.log。")
        self.query_one(Input).focus()

    def action_clear_chat(self) -> None:
        chat_log = self.query_one(RichLog)
        chat_log.clear()
        self.query_one("#trace-tree", Tree).clear()
        self._trace_turn_node = None
        self._trace_tool_nodes.clear()
        self._append_system("聊天记录已清空。")

    def action_toggle_trace(self) -> None:
        trace_tree = self.query_one("#trace-tree", Tree)
        trace_tree.display = not trace_tree.display
        state = "显示" if trace_tree.display else "隐藏"
        self._append_system(f"执行轨迹已{state}。")

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(f"状态: {text}")

    def _append_user(self, text: str) -> None:
        self.query_one(RichLog).write(f"You> {text}")

    def _append_assistant(self, text: str) -> None:
        self.query_one(RichLog).write(f"AI > {text}")

    def _append_system(self, text: str) -> None:
        self.query_one(RichLog).write(f"SYS> {text}")

    @staticmethod
    def _trace_label(text: str) -> Text:
        return Text(text)

    def _current_trace_node(self) -> TreeNode[None]:
        if self._trace_turn_node is None:
            tree = self.query_one("#trace-tree", Tree)
            self._trace_turn += 1
            self._trace_turn_node = tree.root.add(
                self._trace_label(f"第 {self._trace_turn} 轮"),
                expand=True,
            )
        return self._trace_turn_node

    def _append_trace_event(self, event: TraceEvent) -> None:
        if event.kind == "turn_start":
            tree = self.query_one("#trace-tree", Tree)
            self._trace_turn += 1
            self._trace_tool_nodes.clear()
            self._trace_turn_node = tree.root.add(
                self._trace_label(f"第 {self._trace_turn} 轮: {event.summary}"),
                expand=True,
            )
            self._trace_turn_node.add_leaf(
                self._trace_label(f"请求: {event.detail}")
            )
            return

        turn_node = self._current_trace_node()
        if event.kind == "decision":
            turn_node.add_leaf(self._trace_label(f"决策: {event.summary}"))
            self._set_status(event.summary)
            return

        if event.kind == "tool_start":
            tool_node = turn_node.add(
                self._trace_label(f"运行中: {event.tool_name}"),
                expand=False,
            )
            tool_node.add_leaf(
                self._trace_label(f"参数:\n{event.detail or '{}'}")
            )
            self._trace_tool_nodes[event.tool_call_id] = tool_node
            self._set_status(f"正在调用 {event.tool_name}...")
            return

        if event.kind == "tool_result":
            tool_node = self._trace_tool_nodes.get(event.tool_call_id)
            if tool_node is None:
                tool_node = turn_node.add(
                    self._trace_label(event.tool_name or "未知工具"),
                    expand=False,
                )
            elapsed = (
                f"{event.elapsed_ms:.0f} ms"
                if event.elapsed_ms is not None
                else "耗时未知"
            )
            state = "失败" if event.is_error else "完成"
            tool_node.set_label(
                self._trace_label(
                    f"{state}: {event.tool_name} ({elapsed}) | {event.summary}"
                )
            )
            tool_node.add_leaf(
                self._trace_label(f"结果:\n{event.detail or event.summary}")
            )
            self._set_status(f"{event.tool_name} {state}")
            return

        if event.kind == "final":
            final_node = turn_node.add(
                self._trace_label("最终回答已生成"),
                expand=False,
            )
            final_node.add_leaf(
                self._trace_label(event.detail or event.summary)
            )
            self._set_status("正在输出最终回答...")
            return

        if event.kind == "error":
            error_node = turn_node.add(
                self._trace_label(f"执行失败: {event.summary}"),
                expand=False,
            )
            error_node.add_leaf(
                self._trace_label(event.detail or event.summary)
            )

    def _reset_input(self) -> None:
        prompt = self.query_one(Input)
        prompt.disabled = False
        prompt.focus()

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        # 提交后先锁住输入框，避免后台任务还没结束时重复发送。
        raw_message = event.value.strip()
        if not raw_message:
            return

        if raw_message.lower() in {"exit", "quit", ":q"}:
            self.exit()
            return

        if isinstance(event.input, PathInput):
            raw_message = event.input.expand_path_aliases(raw_message)
            event.input.clear_path_aliases()

        message = prepare_cli_message(raw_message)
        event.input.value = ""
        event.input.disabled = True
        self._append_user(message.display_text)
        self._set_status("AI 正在处理...")
        self.run_chat_turn(message.agent_text)

    @work(thread=True, exclusive=True)
    def run_chat_turn(self, message: str) -> None:
        # 模型调用放到后台线程，避免 Textual 主线程卡住。
        reply = ""
        failure = ""
        try:
            for trace_event in self.chat_service.stream(message):
                self.call_from_thread(self._append_trace_event, trace_event)
                if trace_event.kind == "final":
                    reply = trace_event.detail
                elif trace_event.kind == "error":
                    failure = trace_event.detail or trace_event.summary
        except Exception as exc:
            failure = str(exc)

        if reply:
            self.call_from_thread(self._append_assistant, format_paths_for_display(reply))
        elif failure:
            self.call_from_thread(self._append_system, f"处理失败: {failure}")
        else:
            self.call_from_thread(self._append_system, "处理失败: Agent 未返回最终回答")
        self.call_from_thread(self._set_status, "空闲")
        self.call_from_thread(self._reset_input)

def run_cli_shell() -> int:
    """启动 Textual 交互式 CLI shell。"""
    ContractCliShell.live_log_terminal_started = start_live_log_terminal()
    ContractCliShell().run()
    return 0
