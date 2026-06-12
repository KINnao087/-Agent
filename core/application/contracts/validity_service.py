from __future__ import annotations

from typing import Any
from pathlib import Path

from core.infrastructure.contracts import (
    extract_contract_basic_info,
    review_contract_authenticity,
)


def review_contract_validity(
    *,
    linearized_path: str = "",
    contract_text: str = "",
    search_enabled: bool = True,
) -> dict[str, Any]:
    text = contract_text or Path(linearized_path).read_text(encoding="utf-8")
    review = review_contract_authenticity(
        contract_text=text,
        basic_info=extract_contract_basic_info(text),
        search_enabled=search_enabled,
    )
    validity_review = {
        key: value
        for key, value in review.items()
        if key not in {"basic_info", "party_searches"}
    }
    return {
        "linearized_path": linearized_path,
        "basic_info": review["basic_info"],
        "party_searches": review["party_searches"],
        "validity_review": validity_review,
    }
