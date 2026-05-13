from __future__ import annotations

import json
from unittest.mock import patch

from core.domain.contracts import CPSealFragment, CPSealPageResult, CPSealResult
from core.infrastructure.vision.seal.cross_page_review import review_spseal_results


def test_review_spseal_results_merges_vlm_result() -> None:
    fragments = [
        CPSealFragment(
            page_index=1,
            image_path="D:/contracts/page1.png",
            edge="right",
            bbox=[10, 20, 30, 40],
            red_area=1200,
            score=0.8,
        ),
        CPSealFragment(
            page_index=2,
            image_path="D:/contracts/page2.png",
            edge="right",
            bbox=[12, 22, 28, 42],
            red_area=1300,
            score=0.85,
        ),
    ]
    pre_result = CPSealResult(
        status="incomplete",
        page_count=2,
        detected_pages=[1],
        missing_pages=[2],
        main_edge="right",
        risk_level="medium",
        reason="规则预检认为第2页缺少连续候选。",
        page_results=[
            CPSealPageResult(page_index=1, image_path="D:/contracts/page1.png", fragments=[fragments[0]]),
            CPSealPageResult(page_index=2, image_path="D:/contracts/page2.png", fragments=[fragments[1]]),
        ],
    )
    reply = json.dumps(
        {
            "status": "present",
            "risk_level": "low",
            "main_edge": "right",
            "detected_pages": [1, 2],
            "missing_pages": [],
            "reason": "两页右侧均可见连续骑缝章片段。",
            "page_reviews": [],
        },
        ensure_ascii=False,
    )

    with patch(
        "core.infrastructure.vision.seal.cross_page_review.run_images_and_get_reply",
        return_value=reply,
    ) as run_images:
        result = review_spseal_results(fragments, pre_result)

    run_images.assert_called_once()
    call_kwargs = run_images.call_args.kwargs
    assert call_kwargs["image_paths"] == ["D:/contracts/page1.png", "D:/contracts/page2.png"]
    assert "规则预检信息和候选片段" in call_kwargs["user_message"]
    assert "image_order" in call_kwargs["user_message"]
    assert '"image_index": 1' in call_kwargs["user_message"]
    assert '"page_index": 2' in call_kwargs["user_message"]

    assert result.status == "present"
    assert result.risk_level == "low"
    assert result.main_edge == "right"
    assert result.detected_pages == [1, 2]
    assert result.missing_pages == []
    assert "多模态复审：两页右侧均可见连续骑缝章片段。" in result.reason
    assert result.page_results == pre_result.page_results


def test_review_spseal_results_keeps_pre_result_when_vlm_json_invalid() -> None:
    fragment = CPSealFragment(
        page_index=1,
        image_path="D:/contracts/page1.png",
        edge="right",
        bbox=[10, 20, 30, 40],
        red_area=1200,
        score=0.8,
    )
    pre_result = CPSealResult(
        status="incomplete",
        page_count=1,
        detected_pages=[],
        missing_pages=[1],
        main_edge="right",
        risk_level="medium",
        reason="规则预检结果。",
        page_results=[
            CPSealPageResult(page_index=1, image_path="D:/contracts/page1.png", fragments=[fragment]),
        ],
    )

    with patch(
        "core.infrastructure.vision.seal.cross_page_review.run_images_and_get_reply",
        return_value="not json",
    ):
        result = review_spseal_results([fragment], pre_result)

    assert result.status == pre_result.status
    assert result.detected_pages == pre_result.detected_pages
    assert result.missing_pages == pre_result.missing_pages
    assert "多模态复审结果解析失败" in result.reason
