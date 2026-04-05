from __future__ import annotations

from pathlib import Path

from core.domain.contracts.integrity_models import (
    ContractIntegrityResult,
    ContractPageOCR,
    ContractPageText,
)
from core.infrastructure.ai.logger import get_logger
from core.infrastructure.contracts.integrity_review import (
    review_contract_integrity,
    review_contract_seal_integrity,
)
from core.infrastructure.text import linearize_ocr_page, parse_folder_to_json_list
from core.infrastructure.vision.seal import detect_seal_candidates
from core.infrastructure.vision.seal.models import SealCandidate

logger = get_logger("contract-integrity-service")


def build_contract_page_texts(contract_pages: list[ContractPageOCR]) -> list[ContractPageText]:
    """Convert OCR page payloads into ordered linearized page texts."""
    return [
        ContractPageText(page_index=index, page_text=linearize_ocr_page(page))
        for index, page in enumerate(contract_pages, start=1)
    ]


def collect_seal_candidates(contract_pages: list[ContractPageOCR]) -> list[SealCandidate]:
    """Detect seal candidates across all contract pages."""
    candidates: list[SealCandidate] = []
    for page_index, page in enumerate(contract_pages, start=1):
        image_path = page.get("input_path")
        if not isinstance(image_path, str) or not image_path:
            continue
        candidates.extend(
            detect_seal_candidates(image_path=image_path, page_index=page_index)
        )
    return candidates


def check_contract_integrity(
    contract_pages: list[ContractPageOCR],
    seal_candidates: list[SealCandidate] | None = None,
) -> ContractIntegrityResult:
    """Run the contract integrity review use case."""
    page_texts = build_contract_page_texts(contract_pages)
    result = review_contract_integrity(page_texts)
    if seal_candidates:
        result.contract_seal_integrity = review_contract_seal_integrity(page_texts, seal_candidates)
    return result


def check_contract_all(contract_path: str | Path) -> ContractIntegrityResult:
    """Load contract pages from a folder and run full integrity review."""
    contract_dir = Path(contract_path)
    if not contract_dir.exists():
        raise FileNotFoundError(contract_dir)
    if not contract_dir.is_dir():
        raise NotADirectoryError(contract_dir)

    contract_pages = parse_folder_to_json_list(contract_dir)
    seal_candidates = collect_seal_candidates(contract_pages)
    logger.warning("签章候选数量: {}", len(seal_candidates))
    return check_contract_integrity(contract_pages, seal_candidates)
