from __future__ import annotations

import json
import os

from core.infrastructure.ai.config import load_ai_config


def test_load_ai_config_reads_project_env(tmp_path) -> None:
    previous_api_key = os.environ.pop("AI_API_KEY", None)
    try:
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (tmp_path / ".env").write_text("AI_API_KEY=dotenv-test-key\n", encoding="utf-8")
        config_path = config_dir / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "model": "demo-model",
                    "api": {
                        "base_url": "https://example.com/v1",
                        "temperature": 0.1,
                    },
                }
            ),
            encoding="utf-8",
        )

        config = load_ai_config(config_path)

        assert config.model == "demo-model"
        assert config.base_url == "https://example.com/v1"
        assert config.temperature == 0.1
        assert config.api_key == "dotenv-test-key"
    finally:
        os.environ.pop("AI_API_KEY", None)
        if previous_api_key:
            os.environ["AI_API_KEY"] = previous_api_key
