from __future__ import annotations

from core.domain.contracts import CPSealFragment
from core.infrastructure.vision.seal.cross_page_detector import analyze_cross_page_seal_results


def test_analyze_cross_page_seal_results_does_not_treat_total_pages_as_missing_pages() -> None:
    fragments = [
        CPSealFragment(
            page_index=1,
            image_path="D:/contracts/page1.png",
            edge="right",
            bbox=[2400, 100, 20, 80],
            red_area=300,
            score=0.8,
        ),
        CPSealFragment(
            page_index=3,
            image_path="D:/contracts/page3.png",
            edge="right",
            bbox=[2400, 180, 20, 80],
            red_area=260,
            score=0.7,
        ),
    ]

    result = analyze_cross_page_seal_results(fragments)

    assert result.status == "unclear"
    assert result.risk_level == "unknown"
    assert result.detected_pages == [1, 3]
    assert result.missing_pages == []
    assert "不按总页数判断缺失" in result.reason
