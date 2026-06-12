from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

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


def _model_fingerprint() -> str:
    config_path = Path(__file__).resolve().parents[3] / "config" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    return fingerprint_value(
        {
            "model": config.get("model"),
            "base_url": (config.get("api") or {}).get("base_url"),
            "temperature": (config.get("api") or {}).get("temperature"),
        }
    )


def build_default_capability_versions() -> dict[str, dict[str, str]]:
    model = _model_fingerprint()
    return {
        "prepare_contract": {
            "normalizer": "document-normalizer-v1",
            "ocr": "paddleocr-cache-v1",
            "linearizer": "contract-linearizer-v1",
        },
        "check_basic_info": {
            "model": model,
            "prompt": _prompt_fingerprint(BASIC_INFO_PROMPT),
            "compare": "contract-basic-info-compare-v1",
        },
        "check_text_integrity": {
            "model": model,
            "prompt": _prompt_fingerprint(CONTRACT_INTEGRITY_PROMPT),
        },
        "check_contract_seals": {
            "model": model,
            "prompt": _prompt_fingerprint(SEAL_REVIEW_PROMPT),
            "detector": "hybrid-seal-detector-v2",
        },
        "check_cross_page_seal": {
            "model": model,
            "prompt": _prompt_fingerprint(CROSS_PAGE_SEAL_PROMPT),
            "detector": "cross-page-edge-detector-v1",
        },
        "check_contract_authenticity": {
            "model": model,
            "prompt": _prompt_fingerprint(VALIDITY_REVIEW_PROMPT),
            "search": "tavily-advanced-v1",
        },
        "write_review_report": {
            "template": "contract-review-report-v1",
        },
    }
