from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class AIConfig:
    model: str
    base_url: str
    temperature: float = 0.2
    api_key: str = ""


def load_ai_config(config_path: str | Path | None = None) -> AIConfig:
    path = Path(config_path or Path(__file__).resolve().parents[3] / "config" / "config.json")
    if not path.is_absolute():
        path = Path.cwd() / path

    project_root = path.parent.parent if path.parent.name == "config" else path.parent
    load_dotenv(project_root / ".env", override=False)

    data = json.loads(path.read_text(encoding="utf-8"))
    api = data.get("api", {})
    api_key = os.getenv("AI_API_KEY") or api.get("api_key") or ""
    if not api_key:
        raise RuntimeError("AI_API_KEY is not configured")

    return AIConfig(
        model=data["model"],
        base_url=api["base_url"],
        temperature=float(api.get("temperature", 0.2)),
        api_key=api_key,
    )
