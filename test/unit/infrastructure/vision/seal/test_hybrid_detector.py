from __future__ import annotations

import numpy as np

from core.infrastructure.vision.seal.hybrid_detector import (
    HybridSealModel,
    detect_page_seal,
    extract_page_features,
)


def test_extract_page_features_has_stable_shape() -> None:
    image = np.full((320, 240, 3), 255, dtype=np.uint8)
    features, candidates = extract_page_features(image)

    assert features.shape == (2983,)
    assert candidates == []


def test_detect_page_seal_applies_exported_linear_model() -> None:
    image = np.full((320, 240, 3), 255, dtype=np.uint8)
    features, _ = extract_page_features(image)
    model = HybridSealModel(
        mean=np.zeros_like(features),
        scale=np.ones_like(features),
        weights=np.zeros_like(features),
        intercept=2.0,
        threshold=0.8,
    )

    decision = detect_page_seal(image, model)

    assert decision.has_seal
    assert decision.score > 0.8
