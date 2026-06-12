from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

from core.infrastructure.ai import AIConfigRole
from core.infrastructure.vision.seal.models import SealCandidate
from core.infrastructure.vision.seal.seal_check import check_contract_seals


def test_contract_seal_review_sends_page_and_top_candidate_crops() -> None:
    page = Path("normalized/page.png")
    candidates = [
        SealCandidate(
            page_index=1,
            image_path=str(page),
            bbox=[10, 20, 30, 40],
            enhanced_crop_path=f"candidate-{index}.png",
            score=0.9 - index * 0.1,
        )
        for index in range(4)
    ]
    response = Mock()
    response.model_dump.return_value = {"candidate_reviews": []}
    with (
        patch(
            "core.infrastructure.vision.seal.seal_check.normalize_document_images",
            return_value=[page],
        ),
        patch(
            "core.infrastructure.vision.seal.seal_check.detect_seal_candidates",
            return_value=candidates,
        ),
        patch(
            "core.infrastructure.vision.seal.seal_check.invoke_structured",
            return_value=response,
        ) as invoke,
    ):
        check_contract_seals("contract.pdf")

    assert invoke.call_args.kwargs["image_paths"] == [
        page,
        Path("candidate-0.png"),
        Path("candidate-1.png"),
        Path("candidate-2.png"),
    ]
    assert invoke.call_args.kwargs["role"] is AIConfigRole.VISION
