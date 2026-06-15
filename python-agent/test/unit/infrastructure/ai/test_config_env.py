from __future__ import annotations

import json

import pytest

from core.infrastructure.ai.config import AIConfigRole, load_ai_config


ROLE_VARIABLES = (
    "MAIN_AI_API_KEY",
    "MAIN_AI_BASE_URL",
    "MAIN_AI_MODEL",
    "TEXT_AI_API_KEY",
    "TEXT_AI_BASE_URL",
    "TEXT_AI_MODEL",
    "VISION_AI_API_KEY",
    "VISION_AI_BASE_URL",
    "VISION_AI_MODEL",
)


def _write_legacy_config(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "model": "legacy-model",
                "api": {
                    "base_url": "https://legacy.example.com/v1",
                    "temperature": 0.1,
                },
            }
        ),
        encoding="utf-8",
    )
    return config_path


def test_load_ai_config_reads_role_specific_environment(
    tmp_path,
    monkeypatch,
) -> None:
    config_path = _write_legacy_config(tmp_path)
    monkeypatch.setenv("TEXT_AI_API_KEY", "text-key")
    monkeypatch.setenv("TEXT_AI_BASE_URL", "https://text.example.com/v1")
    monkeypatch.setenv("TEXT_AI_MODEL", "deepseek-pro")

    config = load_ai_config(config_path, role=AIConfigRole.TEXT)

    assert config.model == "deepseek-pro"
    assert config.base_url == "https://text.example.com/v1"
    assert config.temperature == 0.1
    assert config.api_key == "text-key"


def test_load_ai_config_falls_back_to_complete_legacy_profile(
    tmp_path,
    monkeypatch,
) -> None:
    config_path = _write_legacy_config(tmp_path)
    for variable in ROLE_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("AI_API_KEY", "legacy-key")

    config = load_ai_config(config_path, role=AIConfigRole.VISION)

    assert config.model == "legacy-model"
    assert config.base_url == "https://legacy.example.com/v1"
    assert config.api_key == "legacy-key"


def test_load_ai_config_preserves_positional_config_path(
    tmp_path,
    monkeypatch,
) -> None:
    config_path = _write_legacy_config(tmp_path)
    for variable in ROLE_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("AI_API_KEY", "legacy-key")

    config = load_ai_config(config_path)

    assert config.model == "legacy-model"


def test_load_ai_config_rejects_partial_role_profile(
    tmp_path,
    monkeypatch,
) -> None:
    config_path = _write_legacy_config(tmp_path)
    monkeypatch.setenv("MAIN_AI_API_KEY", "main-key")
    monkeypatch.delenv("MAIN_AI_BASE_URL", raising=False)
    monkeypatch.delenv("MAIN_AI_MODEL", raising=False)

    with pytest.raises(
        RuntimeError,
        match="MAIN_AI_BASE_URL, MAIN_AI_MODEL",
    ):
        load_ai_config(config_path, role=AIConfigRole.MAIN)
