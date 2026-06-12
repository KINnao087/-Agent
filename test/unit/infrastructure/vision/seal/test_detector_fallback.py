from __future__ import annotations

from unittest.mock import patch

import numpy as np

from core.infrastructure.vision.seal.detector import detect_seal_candidates
from core.infrastructure.vision.seal.hybrid_detector import (
    HybridSealCandidate,
    HybridSealDecision,
)


def test_high_confidence_candidates_reach_multimodal_review_when_page_gate_misses(
    tmp_path,
) -> None:
    image = np.full((600, 800, 3), 255, dtype=np.uint8)
    decision = HybridSealDecision(
        has_seal=False,
        score=0.0001,
        candidates=[
            HybridSealCandidate(
                bbox=[400, 300, 180, 180],
                score=0.84,
                features=[],
            )
        ],
    )

    with (
        patch(
            "core.infrastructure.vision.seal.detector.load_image",
            return_value=image,
        ),
        patch(
            "core.infrastructure.vision.seal.detector.detect_page_seal",
            return_value=decision,
        ),
        patch(
            "core.infrastructure.vision.seal.detector.OUTPUT_DIR",
            tmp_path,
        ),
    ):
        candidates = detect_seal_candidates("page.png", page_index=6)

    assert len(candidates) == 1
    assert candidates[0].bbox == [400, 300, 180, 180]


def test_low_confidence_candidates_stay_blocked_when_page_gate_misses() -> None:
    image = np.full((600, 800, 3), 255, dtype=np.uint8)
    decision = HybridSealDecision(
        has_seal=False,
        score=0.0001,
        candidates=[
            HybridSealCandidate(
                bbox=[400, 300, 180, 180],
                score=0.66,
                features=[],
            )
        ],
    )

    with (
        patch(
            "core.infrastructure.vision.seal.detector.load_image",
            return_value=image,
        ),
        patch(
            "core.infrastructure.vision.seal.detector.detect_page_seal",
            return_value=decision,
        ),
    ):
        candidates = detect_seal_candidates("page.png", page_index=1)

    assert candidates == []


def test_positive_page_gate_keeps_full_page_fallback(tmp_path) -> None:
    image = np.full((600, 800, 3), 255, dtype=np.uint8)
    decision = HybridSealDecision(
        has_seal=True,
        score=0.99,
        candidates=[],
    )

    with (
        patch(
            "core.infrastructure.vision.seal.detector.load_image",
            return_value=image,
        ),
        patch(
            "core.infrastructure.vision.seal.detector.detect_page_seal",
            return_value=decision,
        ),
        patch(
            "core.infrastructure.vision.seal.detector.OUTPUT_DIR",
            tmp_path,
        ),
    ):
        candidates = detect_seal_candidates("page.png", page_index=1)

    assert len(candidates) == 1
    assert candidates[0].bbox == [0, 0, 800, 600]
