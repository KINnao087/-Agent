from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "artifacts" / "logs"
LOG_PATH = LOG_DIR / f"session-{os.getpid()}.log"


class BraceLogger:
    def __init__(self, logger: logging.Logger):
        self._logger = logger

    @staticmethod
    def _message(message: object, *args, **kwargs) -> str:
        text = str(message)
        return text.format(*args, **kwargs) if args or kwargs else text

    def debug(self, message: object, *args, **kwargs) -> None:
        self._logger.debug(self._message(message, *args, **kwargs))

    def info(self, message: object, *args, **kwargs) -> None:
        self._logger.info(self._message(message, *args, **kwargs))

    def warning(self, message: object, *args, **kwargs) -> None:
        self._logger.warning(self._message(message, *args, **kwargs))

    def error(self, message: object, *args, **kwargs) -> None:
        self._logger.error(self._message(message, *args, **kwargs))


def get_logger(name: str) -> BraceLogger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"
        )
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        logger.addHandler(file_handler)
        logger.propagate = False
    return BraceLogger(logger)


def get_latest_log_path() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.touch(exist_ok=True)
    return LOG_PATH


def start_live_log_terminal() -> bool:
    path = str(get_latest_log_path()).replace("'", "''")
    command = (
        "$Host.UI.RawUI.WindowTitle = 'Contract Agent Logs'; "
        f"Get-Content -Path '{path}' -Encoding UTF8 -Wait -Tail 30"
    )
    try:
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NoExit", "-Command", command],
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
    except OSError:
        return False
    return True
