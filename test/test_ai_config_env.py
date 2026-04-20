from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.infrastructure.ai.config import load_agent_config


def test_load_agent_config_reads_ai_api_key_from_project_env(tmp_path) -> None:
    previous_api_key = os.environ.get("AI_API_KEY")
    os.environ.pop("AI_API_KEY", None)

    try:
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)

        (tmp_path / ".env").write_text("AI_API_KEY=dotenv-test-key\n", encoding="utf-8")
        config_path = config_dir / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "provider": "api",
                    "model": "demo-model",
                    "keep_last": 4000,
                    "tool_defs": [],
                    "api": {
                        "base_url": "https://example.com/v1",
                        "api_key": None,
                        "temperature": 0.2,
                    },
                }
            ),
            encoding="utf-8",
        )

        config = load_agent_config(config_path)

        assert config.api.api_key is None
        assert os.environ.get("AI_API_KEY") == "dotenv-test-key"
    finally:
        os.environ.pop("AI_API_KEY", None)
        if previous_api_key is not None:
            os.environ["AI_API_KEY"] = previous_api_key
