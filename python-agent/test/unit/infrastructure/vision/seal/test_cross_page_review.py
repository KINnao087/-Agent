from __future__ import annotations

from unittest.mock import patch

from core.domain.contracts import CPSealFragment, CPSealResult
from core.infrastructure.ai import AIConfigRole
from core.infrastructure.ai.schemas import CrossPageSealReviewResponse
from core.infrastructure.vision.seal.cross_page_review import review_spseal_results


def test_review_spseal_results_merges_structured_vlm_result() -> None:
    fragments = [
        CPSealFragment(
            page_index=1,
            image_path="D:/contracts/page1.png",
            edge="right",
            bbox=[10, 20, 30, 40],
        ),
        CPSealFragment(
            page_index=2,
            image_path="D:/contracts/page2.png",
            edge="right",
            bbox=[12, 22, 28, 42],
        ),
    ]
    pre_result = CPSealResult(
        status="incomplete",
        page_count=2,
        detected_pages=[1],
        missing_pages=[2],
        main_edge="right",
        risk_level="medium",
        reason="规则预检结果",
    )
    response = CrossPageSealReviewResponse(
        status="present",
        risk_level="low",
        main_edge="right",
        detected_pages=[1, 2],
        reason="片段可以拼成完整骑缝章",
    )

    with patch(
        "core.infrastructure.vision.seal.cross_page_review.invoke_structured",
        return_value=response,
    ) as invoke:
        result = review_spseal_results(fragments, pre_result)

    assert result.status == "present"
    assert result.risk_level == "low"
    assert result.detected_pages == [1, 2]
    assert "多模态复审：片段可以拼成完整骑缝章" in result.reason
    assert invoke.call_args.kwargs["image_paths"] == [
        "D:/contracts/page1.png",
        "D:/contracts/page2.png",
    ]
    assert invoke.call_args.kwargs["role"] is AIConfigRole.VISION


def test_review_spseal_results_skips_model_without_fragments() -> None:
    pre_result = CPSealResult(status="missing", reason="没有候选")
    assert review_spseal_results([], pre_result) is pre_result
