from __future__ import annotations

from pathlib import Path

from core.domain.contracts.integrity_models import (
    ContractIntegrityResult,
    ContractPageOCR,
    ContractPageText,
)
from core.infrastructure.contracts import (
    review_contract_seal_integrity,
    review_contract_text_integrity,
)
from core.infrastructure.text import linearize_ocr_page, parse_path_to_json_list
from core.infrastructure.vision.seal import detect_seal_candidates
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
    page_texts = build_contract_page_texts(contract_pages)
    text_result = review_contract_text_integrity(page_texts)
    result = ContractIntegrityResult(
        page_texts=text_result.page_texts,
        contract_continuity=text_result.contract_continuity,
        contract_completeness=text_result.contract_completeness,
        replacement_page=text_result.replacement_page,
        contract_clarity=text_result.contract_clarity,
    )
    if seal_candidates is not None:
        result.contract_seal_integrity = review_contract_seal_integrity(
            page_texts,
            seal_candidates,
        )
    return result


def check_contract_all(contract_path: str | Path) -> ContractIntegrityResult:
    pages = parse_path_to_json_list(contract_path)
    candidates = [
        candidate
        for page_index, page in enumerate(pages, start=1)
        if (image_path := page.get("input_path"))
        for candidate in detect_seal_candidates(str(image_path), page_index)
    ]
    return check_contract_integrity(pages, candidates)
