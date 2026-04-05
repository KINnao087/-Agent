from __future__ import annotations

import inspect
import sys
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


class Logger:
    def __init__(self, name: str = "agent"):
        """初始化一个带默认控制台行为的具名日志器。"""
        self.name = name
        self.level = LogLevel.INFO
        self.enable_color = sys.stdout.isatty()
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
        """在级别允许时渲染并输出一条日志。"""
        if not self._should_log(level):
            return

        rendered = self._render_message(message, *args, **kwargs)
        formatted = self._format_message(level, rendered)
        print(formatted, file=sys.stderr)

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
        prefix = f"{color}[{timestamp}] [{LogLevel.THINKING.value}] [{self.name}] "
        print(prefix, end="", flush=True)

    def stream_thinking(self, chunk: str) -> None:
        """向当前思考流追加一段文本。"""
        if not chunk:
            return

        self.thinking_buffer += chunk
        print(chunk, end="", flush=True)
        if self.thinking_callback:
            self.thinking_callback(chunk)

    def end_thinking_stream(self) -> None:
        """结束当前思考流并清空缓冲内容。"""
        reset = Color.RESET if self.enable_color else ""
        print(reset, flush=True)
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
