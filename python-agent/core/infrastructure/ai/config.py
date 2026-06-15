from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv


class AIConfigRole(str, Enum):
    MAIN = "main"
    TEXT = "text"
    VISION = "vision"


@dataclass(frozen=True, slots=True)
class AIConfig:
    model: str
    base_url: str
    temperature: float = 0.2
    api_key: str = ""


def load_ai_config(
    config_path: str | Path | None = None,
    *,
    role: AIConfigRole = AIConfigRole.MAIN,
) -> AIConfig:
    path = Path(config_path or Path(__file__).resolve().parents[3] / "config" / "config.json")
    if not path.is_absolute():
        path = Path.cwd() / path

    project_root = path.parent.parent if path.parent.name == "config" else path.parent
    load_dotenv(project_root / ".env", override=False)

    data = json.loads(path.read_text(encoding="utf-8"))
    api = data.get("api", {})
    prefix = f"{role.value.upper()}_AI"
    role_values = {
        f"{prefix}_API_KEY": os.getenv(f"{prefix}_API_KEY") or "",
        f"{prefix}_BASE_URL": os.getenv(f"{prefix}_BASE_URL") or "",
        f"{prefix}_MODEL": os.getenv(f"{prefix}_MODEL") or "",
    }
    configured_values = [value for value in role_values.values() if value]
    if configured_values and len(configured_values) != len(role_values):
        missing = [name for name, value in role_values.items() if not value]
        raise RuntimeError(
            f"{role.value} AI configuration is incomplete; missing: "
            + ", ".join(missing)
        )

    if configured_values:
        api_key = role_values[f"{prefix}_API_KEY"]
        base_url = role_values[f"{prefix}_BASE_URL"]
        model = role_values[f"{prefix}_MODEL"]
    else:
        api_key = os.getenv("AI_API_KEY") or api.get("api_key") or ""
        base_url = api.get("base_url") or ""
        model = data.get("model") or ""

    if not api_key:
        raise RuntimeError(
            f"{role.value} AI API key is not configured"
        )
    if not base_url:
        raise RuntimeError(
            f"{role.value} AI base URL is not configured"
        )
    if not model:
        raise RuntimeError(
            f"{role.value} AI model is not configured"
        )

    return AIConfig(
        model=model,
        base_url=base_url,
        temperature=float(api.get("temperature", 0.2)),
        api_key=api_key,
    )
