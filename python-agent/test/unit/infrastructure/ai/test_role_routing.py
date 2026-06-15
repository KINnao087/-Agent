from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from core.domain.contracts.integrity_models import ContractPageText
from core.domain.contracts.models import ContractBasicInfo
from core.infrastructure.ai import AIConfigRole
from core.infrastructure.ai.document import structure_ocr_json
from core.infrastructure.ai.schemas import (
    IntegrityReviewResponse,
    OCRDocumentResult,
    SealPageReviewResponse,
    ValidityReviewResponse,
)
from core.infrastructure.contracts.authenticity_review import (
    review_contract_authenticity,
)
from core.infrastructure.contracts.integrity_review import (
    review_contract_seal_integrity,
    review_contract_text_integrity,
)
from core.infrastructure.vision.seal.models import SealCandidate


def test_document_structuring_uses_text_ai() -> None:
    payload = {
        "input_path": "contract.pdf",
        "contract": [],
        "attachments": [],
        "invoice": [],
    }
    with patch(
        "core.infrastructure.ai.document.invoke_structured",
        return_value=OCRDocumentResult(),
    ) as invoke:
        structure_ocr_json(payload)

    assert invoke.call_args.kwargs["role"] is AIConfigRole.TEXT


def test_text_integrity_uses_text_ai() -> None:
    with patch(
        "core.infrastructure.contracts.integrity_review.invoke_structured",
        return_value=IntegrityReviewResponse(),
    ) as invoke:
        review_contract_text_integrity(
            [ContractPageText(page_index=1, page_text="contract")]
        )

    assert invoke.call_args.kwargs["role"] is AIConfigRole.TEXT


def test_authenticity_review_uses_text_ai() -> None:
    with patch(
        "core.infrastructure.contracts.authenticity_review.invoke_structured",
        return_value=ValidityReviewResponse(),
    ) as invoke:
        review_contract_authenticity(
            contract_text="contract",
            basic_info=ContractBasicInfo(),
            search_enabled=False,
        )

    assert invoke.call_args.kwargs["role"] is AIConfigRole.TEXT


def test_seal_integrity_uses_vision_ai() -> None:
    candidate = SealCandidate(
        page_index=1,
        image_path=Path("page.png"),
        bbox=[0, 0, 10, 10],
        score=0.9,
    )
    with patch(
        "core.infrastructure.contracts.integrity_review.invoke_structured",
        return_value=SealPageReviewResponse(),
    ) as invoke:
        review_contract_seal_integrity(
            [ContractPageText(page_index=1, page_text="contract")],
            [candidate],
        )

    assert invoke.call_args.kwargs["role"] is AIConfigRole.VISION
