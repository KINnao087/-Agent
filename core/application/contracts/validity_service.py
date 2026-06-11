from __future__ import annotations

from typing import Any

from core.application.workflows.validity import VALIDITY_GRAPH


def review_contract_validity(
    *,
    linearized_path: str = "",
    contract_text: str = "",
    search_enabled: bool = True,
) -> dict[str, Any]:
    state = VALIDITY_GRAPH.invoke(
        {
            "linearized_path": linearized_path,
            "contract_text": contract_text,
            "search_enabled": search_enabled,
        }
    )
    return {
        "linearized_path": linearized_path,
        "basic_info": state["basic_info"],
        "party_searches": state["party_searches"],
        "validity_review": state["validity_review"],
    }
