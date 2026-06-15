from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from core.infrastructure.vision.seal.seal_check import check_contract_seals


def test_contract_seal_review_uses_normalized_png_pages() -> None:
    normalized_page = Path("normalized/page.png")
    with (
        patch(
            "core.infrastructure.vision.seal.seal_check.normalize_document_images",
            return_value=[normalized_page],
        ) as normalize,
        patch(
            "core.infrastructure.vision.seal.seal_check.detect_seal_candidates",
            return_value=[],
        ) as detect,
    ):
        result = check_contract_seals("contract.jpg")

    normalize.assert_called_once_with("contract.jpg")
    detect.assert_called_once_with(
        image_path=normalized_page,
        page_index=1,
    )
    payload = json.loads(result["output"])
    assert payload["page_results"][0]["image_path"] == str(normalized_page)
