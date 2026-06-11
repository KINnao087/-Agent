from __future__ import annotations

from pathlib import Path

from core.application.workflows.integrity import INTEGRITY_GRAPH
from core.domain.contracts.integrity_models import (
    ContractIntegrityResult,
    ContractPageOCR,
    ContractPageText,
)
from core.infrastructure.text import linearize_ocr_page
from core.infrastructure.vision.seal.models import SealCandidate


def build_contract_page_texts(
    contract_pages: list[ContractPageOCR],
) -> list[ContractPageText]:
    return [
        ContractPageText(page_index=index, page_text=linearize_ocr_page(page))
        for index, page in enumerate(contract_pages, start=1)
    ]


def check_contract_integrity(
    contract_pages: list[ContractPageOCR],
    seal_candidates: list[SealCandidate] | None = None,
) -> ContractIntegrityResult:
    state = INTEGRITY_GRAPH.invoke(
        {
            "contract_pages": contract_pages,
            "seal_candidates": seal_candidates or [],
            "review_seals": seal_candidates is not None,
            "detect_seals": False,
        }
    )
    return state["result"]


def check_contract_all(contract_path: str | Path) -> ContractIntegrityResult:
    state = INTEGRITY_GRAPH.invoke(
        {
            "contract_path": str(contract_path),
            "detect_seals": True,
            "review_seals": True,
        }
    )
    return state["result"]
