from __future__ import annotations

import hashlib
import json
from typing import Any

from core.infrastructure.ai import AIConfigRole, load_ai_config
from core.infrastructure.ai.prompts import (
    BASIC_INFO_PROMPT,
    CONTRACT_INTEGRITY_PROMPT,
    CROSS_PAGE_SEAL_PROMPT,
    SEAL_REVIEW_PROMPT,
    VALIDITY_REVIEW_PROMPT,
)


def fingerprint_value(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=repr,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _prompt_fingerprint(prompt: Any) -> str:
    return fingerprint_value([repr(message) for message in prompt.messages])


def _model_fingerprint(role: AIConfigRole) -> str:
    config = load_ai_config(role=role)
    return fingerprint_value(
        {
            "role": role.value,
            "model": config.model,
            "base_url": config.base_url,
            "temperature": config.temperature,
        }
    )


def build_default_capability_versions() -> dict[str, dict[str, str]]:
    text_model = _model_fingerprint(AIConfigRole.TEXT)
    vision_model = _model_fingerprint(AIConfigRole.VISION)
    text_structured_call = (
        "function-calling-provider-thinking-disabled-v3"
    )
    vision_structured_call = "function-calling-thinking-disabled-v2"
    return {
        "prepare_contract": {
            "normalizer": "document-normalizer-v1",
            "ocr": "paddleocr-cache-v1",
            "linearizer": "contract-linearizer-v1",
        },
        "check_basic_info": {
            "role": AIConfigRole.TEXT.value,
            "model": text_model,
            "structured_call": text_structured_call,
            "prompt": _prompt_fingerprint(BASIC_INFO_PROMPT),
            "compare": "contract-basic-info-compare-v1",
        },
        "check_text_integrity": {
            "role": AIConfigRole.TEXT.value,
            "model": text_model,
            "structured_call": text_structured_call,
            "prompt": _prompt_fingerprint(CONTRACT_INTEGRITY_PROMPT),
        },
        "check_contract_seals": {
            "role": AIConfigRole.VISION.value,
            "model": vision_model,
            "structured_call": vision_structured_call,
            "prompt": _prompt_fingerprint(SEAL_REVIEW_PROMPT),
            "detector": "hybrid-seal-detector-v3",
        },
        "check_cross_page_seal": {
            "role": AIConfigRole.VISION.value,
            "model": vision_model,
            "structured_call": vision_structured_call,
            "prompt": _prompt_fingerprint(CROSS_PAGE_SEAL_PROMPT),
            "detector": "cross-page-edge-detector-v1",
        },
        "check_contract_authenticity": {
            "role": AIConfigRole.TEXT.value,
            "model": text_model,
            "structured_call": text_structured_call,
            "prompt": _prompt_fingerprint(VALIDITY_REVIEW_PROMPT),
            "search": "tavily-advanced-v1",
        },
        "write_review_report": {
            "template": "contract-review-report-v1",
        },
    }
