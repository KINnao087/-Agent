from __future__ import annotations

import inspect
import re
import subprocess
import sys
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Callable


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    AGENT = "AGENT"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    THINKING = "THINKING"


class Color:
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_MAGENTA = "\033[95m"
    BG_WHITE = "\033[47m"


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_LOG_DIR = _PROJECT_ROOT / "Log"
_SESSION_STAMP = time.strftime("%Y%m%d-%H%M%S")
_LATEST_LOG_PATH = _LOG_DIR / "latest.log"
_SESSION_LOG_PATH = _LOG_DIR / f"session-{_SESSION_STAMP}.log"
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_LOG_LOCK = threading.RLock()
_LOG_FILES_READY = False
_TAIL_TERMINAL_STARTED = False


def _strip_ansi(text: str) -> str:
    """移除 ANSI 颜色控制符，避免写入日志文件的内容出现乱码。"""
    return _ANSI_RE.sub("", text)


def _session_banner() -> str:
    """为每次进程启动生成一段日志头，便于区分不同运行会话。"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    return f"=== Log session started at {timestamp} ===\n"


def _ensure_log_files() -> None:
    """确保项目根目录下的 Log 目录和当前会话日志文件存在。"""
    global _LOG_FILES_READY
    with _LOG_LOCK:
        if _LOG_FILES_READY:
            return

        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        banner = _session_banner()
        _LATEST_LOG_PATH.write_text(banner, encoding="utf-8")
        _SESSION_LOG_PATH.write_text(banner, encoding="utf-8")
        _LOG_FILES_READY = True


def _write_text_to_log_files(text: str) -> None:
    """把日志文本同时写入 latest.log 和本次会话日志。"""
    _ensure_log_files()
    clean_text = _strip_ansi(text)
    with _LOG_LOCK:
        for path in (_LATEST_LOG_PATH, _SESSION_LOG_PATH):
            with path.open("a", encoding="utf-8") as file:
                file.write(clean_text)


def get_log_dir() -> Path:
    """返回项目日志目录。"""
    _ensure_log_files()
    return _LOG_DIR


def get_latest_log_path() -> Path:
    """返回 latest.log 的绝对路径。"""
    _ensure_log_files()
    return _LATEST_LOG_PATH


def get_session_log_path() -> Path:
    """返回当前进程会话日志的绝对路径。"""
    _ensure_log_files()
    return _SESSION_LOG_PATH


def start_live_log_terminal() -> bool:
    """在 Windows 上拉起一个新的 PowerShell 窗口，实时 tail latest.log。"""
    global _TAIL_TERMINAL_STARTED
    _ensure_log_files()

    with _LOG_LOCK:
        if _TAIL_TERMINAL_STARTED:
            return False

        escaped_path = str(_LATEST_LOG_PATH).replace("'", "''")
        command = (
            "$Host.UI.RawUI.WindowTitle = 'Contract Agent Logs'; "
            f"if (-not (Test-Path '{escaped_path}')) "
            f"{{ New-Item -ItemType File -Path '{escaped_path}' -Force | Out-Null }}; "
            f"Write-Host 'Tailing {escaped_path}' -ForegroundColor Cyan; "
            f"Get-Content -Path '{escaped_path}' -Wait -Tail 30"
        )

        try:
            subprocess.Popen(
                ["powershell.exe", "-NoExit", "-Command", command],
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
        except Exception:
            return False

        _TAIL_TERMINAL_STARTED = True
        return True


class Logger:
    def __init__(self, name: str = "agent"):
        """初始化一个同时支持终端输出和文件落盘的具名日志器。"""
        self.name = name
        self.level = LogLevel.INFO
        self.enable_color = sys.stderr.isatty()
        self.thinking_callback: Callable[[str], None] | None = None
        self.thinking_buffer = ""

    def _get_color(self, level: LogLevel) -> str:
        """返回指定日志级别对应的 ANSI 颜色前缀。"""
        if not self.enable_color:
            return ""

        color_map = {
            LogLevel.DEBUG: Color.BRIGHT_BLACK,
            LogLevel.INFO: Color.BRIGHT_BLUE,
            LogLevel.AGENT: Color.GREEN,
            LogLevel.WARNING: Color.BRIGHT_YELLOW,
            LogLevel.ERROR: Color.BRIGHT_RED,
            LogLevel.CRITICAL: Color.RED + Color.BG_WHITE,
            LogLevel.THINKING: Color.BRIGHT_MAGENTA,
        }
        return color_map.get(level, Color.RESET)

    def _caller_location(self) -> str:
        """查找首个不在当前日志模块内的调用位置。"""
        current_file = Path(__file__).resolve()
        frame = inspect.currentframe()
        try:
            if frame is not None:
                frame = frame.f_back
            while frame is not None:
                filename = Path(frame.f_code.co_filename).resolve()
                if filename != current_file:
                    return f"{filename.name}:{frame.f_lineno}"
                frame = frame.f_back
            return "unknown:0"
        finally:
            del frame

    def _format_message(self, level: LogLevel, message: str) -> str:
        """组装包含时间、级别、名称和调用位置的日志文本。"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        color = self._get_color(level)
        reset = Color.RESET if self.enable_color else ""
        location = self._caller_location()
        return f"{color}[{timestamp}] [{level.value}] [{self.name}] [{location}] {message}{reset}"

    def _should_log(self, level: LogLevel) -> bool:
        """判断当前日志级别是否允许输出该消息。"""
        level_order = {
            LogLevel.DEBUG: 0,
            LogLevel.INFO: 1,
            LogLevel.AGENT: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3,
            LogLevel.CRITICAL: 4,
            LogLevel.THINKING: 5,
        }
        return level_order.get(level, 0) >= level_order.get(self.level, 0)

    def _render_message(self, message: object, *args, **kwargs) -> str:
        """安全地渲染带格式化参数的日志消息。"""
        text = "" if message is None else str(message)
        if not args and not kwargs:
            return text
        try:
            return text.format(*args, **kwargs)
        except Exception as exc:
            return (
                f"{text} [log format error: {exc}; "
                f"args={args!r}; kwargs={kwargs!r}]"
            )

    def log(self, level: LogLevel, message: object, *args, **kwargs) -> None:
        """在级别允许时渲染并同时输出到终端和日志文件。"""
        if not self._should_log(level):
            return

        rendered = self._render_message(message, *args, **kwargs)
        formatted = self._format_message(level, rendered)
        print(formatted, file=sys.stderr)
        _write_text_to_log_files(formatted + "\n")

    def debug(self, message: object, *args, **kwargs) -> None:
        """输出 DEBUG 级别日志。"""
        self.log(LogLevel.DEBUG, message, *args, **kwargs)

    def info(self, message: object, *args, **kwargs) -> None:
        """输出 INFO 级别日志。"""
        self.log(LogLevel.INFO, message, *args, **kwargs)

    def agent(self, message: object, *args, **kwargs) -> None:
        """输出 AGENT 级别日志。"""
        self.log(LogLevel.AGENT, message, *args, **kwargs)

    def warning(self, message: object, *args, **kwargs) -> None:
        """输出 WARNING 级别日志。"""
        self.log(LogLevel.WARNING, message, *args, **kwargs)

    def error(self, message: object, *args, **kwargs) -> None:
        """输出 ERROR 级别日志。"""
        self.log(LogLevel.ERROR, message, *args, **kwargs)

    def critical(self, message: object, *args, **kwargs) -> None:
        """输出 CRITICAL 级别日志。"""
        self.log(LogLevel.CRITICAL, message, *args, **kwargs)

    def thinking(self, message: object, *args, **kwargs) -> None:
        """输出 THINKING 级别日志。"""
        self.log(LogLevel.THINKING, message, *args, **kwargs)

    def start_thinking_stream(self) -> None:
        """开始一段单行的思考流输出。"""
        self.thinking_buffer = ""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        color = self._get_color(LogLevel.THINKING)
        reset = Color.RESET if self.enable_color else ""
        prefix = f"{color}[{timestamp}] [{LogLevel.THINKING.value}] [{self.name}] {reset}"
        print(prefix, end="", flush=True)
        _write_text_to_log_files(prefix)

    def stream_thinking(self, chunk: str) -> None:
        """向当前思考流追加一段文本。"""
        if not chunk:
            return

        self.thinking_buffer += chunk
        print(chunk, end="", flush=True)
        _write_text_to_log_files(chunk)
        if self.thinking_callback:
            self.thinking_callback(chunk)

    def end_thinking_stream(self) -> None:
        """结束当前思考流并清空缓冲内容。"""
        reset = Color.RESET if self.enable_color else ""
        print(reset, flush=True)
        _write_text_to_log_files("\n")
        if self.thinking_callback and self.thinking_buffer:
            self.thinking_callback(self.thinking_buffer)
        self.thinking_buffer = ""

    def set_level(self, level: LogLevel) -> None:
        """更新日志输出阈值。"""
        self.level = level

    def set_thinking_callback(self, callback: Callable[[str], None] | None) -> None:
        """注册一个可选的思考流回调函数。"""
        self.thinking_callback = callback


_LOGGERS: dict[str, Logger] = {}


def get_logger(name: str = "agent") -> Logger:
    """返回指定名称对应的共享日志器实例。"""
    logger = _LOGGERS.get(name)
    if logger is None:
        logger = Logger(name)
        _LOGGERS[name] = logger
    return logger


def set_log_level(level: LogLevel) -> None:
    """更新默认日志器的输出级别。"""
    get_logger().set_level(level)


def set_thinking_callback(callback: Callable[[str], None] | None) -> None:
    """为默认日志器设置思考流回调。"""
    get_logger().set_thinking_callback(callback)


def start_thinking_stream() -> None:
    """在默认日志器上开始思考流输出。"""
    get_logger().start_thinking_stream()


def stream_thinking(chunk: str) -> None:
    """向默认日志器转发一段思考流文本。"""
    get_logger().stream_thinking(chunk)


def end_thinking_stream() -> None:
    """结束默认日志器上的思考流输出。"""
    get_logger().end_thinking_stream()
