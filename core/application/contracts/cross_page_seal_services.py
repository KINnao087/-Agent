from pathlib import Path

from core.domain.contracts import CPSealResult
from core.infrastructure.text import normalize_document_images
from core.infrastructure.vision.seal import review_cross_page_seal_images


def check_cpseal_services(input_path: str | Path) -> CPSealResult:
    return review_cross_page_seal_images(
        normalize_document_images(input_path)
    )
