from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from urllib.parse import unquote, urlparse

from core.application.agent import create_cli_chat_service
from core.infrastructure.ai import get_logger
from core.infrastructure.ai.logger import get_latest_log_path, start_live_log_terminal

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
from textual.widgets import Footer, Header, Input, RichLog, Static

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
    """返回路径用于界面展示的短名称。"""
    cleaned = _clean_dragged_path(path_text)
    if re.match(r"^(?:[A-Za-z]:[\\/]|\\\\)", cleaned):
        name = PureWindowsPath(cleaned).name
    else:
        name = Path(cleaned).name
    return name or cleaned


def prepare_cli_message(raw_message: str) -> PreparedCliMessage:
    """把用户输入中的文件路径转成绝对路径，同时生成短路径展示文本。"""
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
        normalized_parts.append(f'"{absolute_path}"')
        display_parts.append(f"[{_file_display_name(path_text)}]")
        cursor = end

    normalized_parts.append(raw_message[cursor:])
    display_parts.append(raw_message[cursor:])
    return PreparedCliMessage(
        agent_text="".join(normalized_parts).strip(),
        display_text="".join(display_parts).strip(),
    )


def format_paths_for_display(text: str) -> str:
    """把任意文本里的绝对路径压缩成 [文件名]，用于聊天窗口展示。"""
    return prepare_cli_message(text).display_text


def normalize_paste_for_input(text: str) -> str:
    """把粘贴或终端拖入的路径文本转换成适合单行输入框的文本。"""
    compact_text = " ".join((text or "").splitlines()).strip()
    if not compact_text:
        return ""
    return prepare_cli_message(compact_text).agent_text


class PathInput(Input):
    """支持把终端粘贴进来的文件路径规范化成绝对路径。"""

    def on_paste(self, event: events.Paste) -> None:
        pasted_text = normalize_paste_for_input(event.text)
        if not pasted_text:
            event.prevent_default()
            event.stop()
            return

        self.insert_text_at_cursor(pasted_text)
        event.prevent_default()
        event.stop()


class ContractCliShell(App[None]):
    TITLE = "Contract Agent Shell"
    # chat_service 在 shell 生命周期内复用，保存多轮对话上下文。
    chat_service = create_cli_chat_service()
    live_log_terminal_started = False
    # SUB_TITLE = "无参数默认进入的 CLI 对话模式"
    CSS = """
    Screen {
        layout: vertical;
    }

    #chat-log {
        height: 1fr;
        border: solid $accent;
        padding: 1 2;
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
    ]

    def compose(self) -> ComposeResult:
        # 最小可用布局：聊天记录、状态区、输入框。
        yield Header(show_clock=True)
        yield RichLog(id="chat-log", wrap=True, markup=False, highlight=False)
        yield Static("状态: 空闲", id="status")
        yield PathInput(
            placeholder="输入问题，或直接描述要处理的合同文件路径和需求...",
            id="prompt",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._append_system("已进入交互模式。直接输入需求；Ctrl+L 清屏，Ctrl+C 退出。")
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
        self._append_system("聊天记录已清空。")

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(f"状态: {text}")

    def _append_user(self, text: str) -> None:
        self.query_one(RichLog).write(f"You> {text}")

    def _append_assistant(self, text: str) -> None:
        self.query_one(RichLog).write(f"AI > {text}")

    def _append_system(self, text: str) -> None:
        self.query_one(RichLog).write(f"SYS> {text}")

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

        message = prepare_cli_message(raw_message)
        event.input.value = ""
        event.input.disabled = True
        self._append_user(message.display_text)
        self._set_status("AI 正在处理...")
        self.run_chat_turn(message.agent_text)

    @work(thread=True, exclusive=True)
    def run_chat_turn(self, message: str) -> None:
        # 模型调用放到后台线程，避免 Textual 主线程卡住。
        try:
            reply = self.chat_service.ask(message)
        except Exception as exc:
            self.call_from_thread(self._append_system, f"处理失败: {exc}")
        else:
            self.call_from_thread(self._append_assistant, format_paths_for_display(reply))
        finally:
            self.call_from_thread(self._set_status, "空闲")
            self.call_from_thread(self._reset_input)

def run_cli_shell() -> int:
    """启动 Textual 交互式 CLI shell。"""
    ContractCliShell.live_log_terminal_started = start_live_log_terminal()
    ContractCliShell().run()
    return 0
