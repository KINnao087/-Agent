from __future__ import annotations

import json
from typing import Any

from core.domain.contracts.models import ContractBasicInfo
from core.infrastructure.ai import AIConfigRole, invoke_structured
from core.infrastructure.ai.prompts import VALIDITY_REVIEW_PROMPT
from core.infrastructure.ai.schemas import ValidityReviewResponse
from core.infrastructure.web_searcher.searcher import tavily_search


def review_contract_authenticity(
    *,
    contract_text: str,
    basic_info: ContractBasicInfo | dict[str, Any],
    search_enabled: bool = True,
) -> dict[str, Any]:
    info = (
        basic_info
        if isinstance(basic_info, ContractBasicInfo)
        else ContractBasicInfo.model_validate(basic_info)
    )
    names = {
        party.name
        for party in (info.seller, info.buyer)
        if party.name
    }
    party_searches = []
    if search_enabled:
        party_searches = [
            {
                "party_name": name,
                "results": tavily_search(
                    q=f"{name} 工商信息 法定代表人 失信 被执行人 经营异常",
                    sdepth="advanced",
                ).get("results", []),
            }
            for name in sorted(names)
        ]
    response = invoke_structured(
        VALIDITY_REVIEW_PROMPT,
        ValidityReviewResponse,
        {
            "basic_info": json.dumps(info.model_dump(), ensure_ascii=False, indent=2),
            "party_searches": json.dumps(party_searches, ensure_ascii=False, indent=2),
            "contract_text": contract_text[:16000],
        },
        role=AIConfigRole.TEXT,
    )
    return {
        "basic_info": info.model_dump(),
        "party_searches": party_searches,
        **response.model_dump(),
    }
