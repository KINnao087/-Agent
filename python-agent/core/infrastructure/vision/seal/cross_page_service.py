from __future__ import annotations

from pathlib import Path

from core.domain.contracts import CPSealResult

from .cross_page_detector import (
    analyze_cross_page_seal_results,
    detect_cross_page_seal_fragments,
)
from .cross_page_review import review_spseal_results


def review_cross_page_seal_images(
    image_paths: list[Path],
) -> CPSealResult:
    fragments = [
        fragment
        for page_index, image_path in enumerate(image_paths, start=1)
        for fragment in detect_cross_page_seal_fragments(image_path, page_index)
    ]
    pre_result = analyze_cross_page_seal_results(fragments)
    pre_result.page_count = len(image_paths)
    return review_spseal_results(fragments, pre_result)
