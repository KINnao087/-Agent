from __future__ import annotations

import json
from dataclasses import asdict

from core.domain.contracts import CPSealFragment, CPSealResult
from core.infrastructure.ai import invoke_structured
from core.infrastructure.ai.prompts import CROSS_PAGE_SEAL_PROMPT
from core.infrastructure.ai.schemas import CrossPageSealReviewResponse


def review_spseal_results(
    fragments: list[CPSealFragment],
    pre_result: CPSealResult,
) -> CPSealResult:
    if not fragments:
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
        "fragments": [asdict(fragment) for fragment in fragments],
    }
    response = invoke_structured(
        CROSS_PAGE_SEAL_PROMPT,
        CrossPageSealReviewResponse,
        {"payload": json.dumps(payload, ensure_ascii=False, indent=2)},
        image_paths=[fragment.image_path for fragment in fragments],
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
