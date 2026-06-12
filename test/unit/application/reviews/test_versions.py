from __future__ import annotations

from unittest.mock import patch

from core.application.reviews.versions import (
    build_default_capability_versions,
    fingerprint_value,
)
from core.infrastructure.ai import AIConfig, AIConfigRole


def test_fingerprint_value_is_stable_and_changes_with_content() -> None:
    assert fingerprint_value({"b": 2, "a": 1}) == fingerprint_value(
        {"a": 1, "b": 2}
    )
    assert fingerprint_value({"a": 1}) != fingerprint_value({"a": 2})


def test_default_versions_track_model_prompts_and_algorithms() -> None:
    versions = build_default_capability_versions()

    assert versions["prepare_contract"]["ocr"]
    assert versions["check_basic_info"]["model"]
    assert versions["check_basic_info"]["prompt"]
    assert versions["check_text_integrity"]["prompt"]
    assert versions["check_contract_seals"]["detector"]
    assert versions["check_cross_page_seal"]["detector"]
    assert versions["check_contract_authenticity"]["prompt"]
    assert versions["write_review_report"]["template"]


def test_default_versions_fingerprint_text_and_vision_models_separately() -> None:
    configs = {
        AIConfigRole.TEXT: AIConfig(
            model="deepseek-pro",
            base_url="https://text.example.com/v1",
            api_key="text-key",
        ),
        AIConfigRole.VISION: AIConfig(
            model="qwen3.5-flash",
            base_url="https://vision.example.com/v1",
            api_key="vision-key",
        ),
    }

    with patch(
        "core.application.reviews.versions.load_ai_config",
        side_effect=lambda *, role: configs[role],
    ):
        versions = build_default_capability_versions()

    assert (
        versions["check_basic_info"]["model"]
        == versions["check_contract_authenticity"]["model"]
    )
    assert (
        versions["check_basic_info"]["model"]
        != versions["check_contract_seals"]["model"]
    )
    assert versions["check_basic_info"]["role"] == "text"
    assert versions["check_contract_seals"]["role"] == "vision"
