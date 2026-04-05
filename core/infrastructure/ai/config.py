from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .logger import get_logger


@dataclass(slots=True)
class ApiConfig:
    base_url: str = ""
    temperature: float = 0.2
    api_key: str | None = None


@dataclass(slots=True)
class AgentConfig:
    model: str
    tool_defs: list[dict]
    base_system: str = ""
    keep_last: int = 4000
    provider: str = "api"
    api: ApiConfig = field(default_factory=ApiConfig)

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "AgentConfig":
        """校验原始配置字典并转换成 AgentConfig。"""
        if not isinstance(config, dict):
            raise TypeError("config must be a JSON object")

        required_keys = ("model", "tool_defs")
        missing = [key for key in required_keys if key not in config]
        if missing:
            raise KeyError(f"config missing required keys: {', '.join(missing)}")

        model = config["model"]
        base_system = config.get("base_system", "")
        tool_defs = config["tool_defs"]

        if not isinstance(model, str) or not model.strip():
            raise TypeError("config field 'model' must be a non-empty string")
        if not isinstance(base_system, str):
            raise TypeError("config field 'base_system' must be a string")
        if not isinstance(tool_defs, list):
            raise TypeError("config field 'tool_defs' must be a list")

        provider = str(config.get("provider") or "api").strip()
        if not provider:
            raise TypeError("config field 'provider' must be a non-empty string")

        raw_api = config.get("api") or {}
        if not isinstance(raw_api, dict):
            raise TypeError("config field 'api' must be an object or null")

        api = ApiConfig(
            base_url=str(raw_api.get("base_url") or ""),
            temperature=float(raw_api.get("temperature", 0.2)),
            api_key=raw_api.get("api_key"),
        )
        if api.api_key is not None and not isinstance(api.api_key, str):
            raise TypeError("config field 'api.api_key' must be a string or null")

        keep_last = int(config.get("keep_last", 4000))
        if keep_last <= 0:
            raise ValueError("config field 'keep_last' must be positive")

        return cls(
            model=model.strip(),
            base_system=base_system,
            tool_defs=tool_defs,
            keep_last=keep_last,
            provider=provider,
            api=api,
        )


def load_agent_config(config_path: str | Path | None = None) -> AgentConfig:
    """加载项目默认配置或用户指定路径下的配置文件。"""
    logger = get_logger("ai-config")
    if config_path is None:
        config_path = Path(__file__).resolve().parents[2] / "config" / "config.json"
    else:
        config_path = Path(config_path)
        if not config_path.is_absolute():
            config_path = Path.cwd() / config_path

    try:
        with open(config_path, "r", encoding="utf-8") as file:
            content = file.read().strip()
            if not content:
                raise ValueError(f"config file is empty: {config_path}")
            raw_config = json.loads(content)
    except FileNotFoundError:
        logger.error("config file not found: {}", config_path)
        raise
    except json.JSONDecodeError as exc:
        logger.error("failed to parse config json: {} ({})", config_path, str(exc))
        raise

    return AgentConfig.from_dict(raw_config)
