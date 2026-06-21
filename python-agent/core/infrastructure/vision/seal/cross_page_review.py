from __future__ import annotations

import json
from dataclasses import asdict

from core.domain.contracts import CPSealFragment, CPSealResult
from core.infrastructure.ai import AIConfigRole, invoke_structured
from core.infrastructure.ai.prompts import CROSS_PAGE_SEAL_PROMPT
from core.infrastructure.ai.schemas import CrossPageSealReviewResponse


def _select_review_fragments(
    fragments: list[CPSealFragment],
    pre_result: CPSealResult,
) -> list[CPSealFragment]:
    detected_pages = set(pre_result.detected_pages)
    main_edge = pre_result.main_edge
    selected = [
        fragment
        for fragment in fragments
        if fragment.score > 0
        and fragment.edge != "unknown"
        and (not detected_pages or fragment.page_index in detected_pages)
        and (main_edge == "unknown" or fragment.edge == main_edge)
    ]
    if not selected:
        return []

    selected.sort(
        key=lambda fragment: (
            fragment.page_index,
            -fragment.score,
            -fragment.red_area,
        )
    )

    per_page_limit = 3
    page_counts: dict[int, int] = {}
    limited: list[CPSealFragment] = []
    for fragment in selected:
        count = page_counts.get(fragment.page_index, 0)
        if count >= per_page_limit:
            continue
        limited.append(fragment)
        page_counts[fragment.page_index] = count + 1
    return limited


def review_spseal_results(
    fragments: list[CPSealFragment],
    pre_result: CPSealResult,
) -> CPSealResult:
    if not fragments:
        return pre_result

    review_fragments = _select_review_fragments(fragments, pre_result)
    if not review_fragments:
        return pre_result

    payload = {
        "rule_result": {
            "status": pre_result.status,
            "page_count": pre_result.page_count,
            "detected_pages": pre_result.detected_pages,
            "missing_pages": pre_result.missing_pages,
            "main_edge": pre_result.main_edge,
            "risk_level": pre_result.risk_level,
            "reason": pre_result.reason,
        },
        "fragments": [asdict(fragment) for fragment in review_fragments],
    }
    review_image_paths = list(
        dict.fromkeys(fragment.image_path for fragment in review_fragments)
    )
    response = invoke_structured(
        CROSS_PAGE_SEAL_PROMPT,
        CrossPageSealReviewResponse,
        {"payload": json.dumps(payload, ensure_ascii=False, indent=2)},
        image_paths=review_image_paths,
        role=AIConfigRole.VISION,
    )
    return CPSealResult(
        status=response.status,
        page_count=pre_result.page_count,
        detected_pages=response.detected_pages,
        missing_pages=response.missing_pages,
        main_edge=response.main_edge,
        risk_level=response.risk_level,
        reason=f"多模态复审：{response.reason}；规则预检：{pre_result.reason}",
        page_results=pre_result.page_results,
    )
