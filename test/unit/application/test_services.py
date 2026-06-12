from __future__ import annotations

from unittest.mock import patch

from core.application.contracts import (
    check_basic_info,
    check_contract_integrity,
    review_contract_validity,
)
from core.application.contracts.cross_page_seal_services import check_cpseal_services
from core.application.documents import parse_documents_to_structured_json
from core.application.workflows.chat import build_chat_graph
from core.domain.contracts import CPSealResult
from core.domain.contracts.integrity_models import TextIntegrityReviewResult
from core.domain.contracts.models import ContractBasicInfo
from core.infrastructure.ai import AIConfigRole


def test_basic_info_service_runs_extract_compare_and_summary() -> None:
    extracted = ContractBasicInfo(contract_no="HT-1")
    platform = ContractBasicInfo(contract_no="HT-1")
    with patch(
        "core.application.contracts.basic_info_service.extract_contract_basic_info",
        return_value=extracted,
    ):
        response = check_basic_info("合同", platform)

    assert response.contract_basic_info == extracted
    assert response.summary.matched_fields == 1


def test_parse_documents_service_passes_loaded_payload_to_structurer() -> None:
    payload = {
        "input_path": "contract.pdf",
        "contract": [],
        "attachments": [],
        "invoice": [],
        "linearized": {},
    }
    structured = {"structured": {"doc_type": "contract"}}
    with (
        patch(
            "core.application.documents.parse_service.load_document_payload",
            return_value=payload,
        ),
        patch(
            "core.application.documents.parse_service.structure_ocr_json",
            return_value=structured,
        ) as structure,
    ):
        result = parse_documents_to_structured_json("contract.pdf")

    structure.assert_called_once_with(payload)
    assert result.structured_json == structured


def test_chat_graph_is_the_only_application_graph() -> None:
    with patch("core.application.workflows.chat.build_chat_model") as build:
        graph = build_chat_graph()

    assert {"assistant", "tools"} <= set(graph.get_graph().nodes)
    build.assert_called_once_with(role=AIConfigRole.MAIN)


def test_integrity_service_combines_text_and_optional_seal_results() -> None:
    text_result = TextIntegrityReviewResult()
    with (
        patch(
            "core.application.contracts.integrity_service.linearize_ocr_page",
            return_value="page text",
        ),
        patch(
            "core.application.contracts.integrity_service.review_contract_text_integrity",
            return_value=text_result,
        ) as review_text,
        patch(
            "core.application.contracts.integrity_service.review_contract_seal_integrity",
        ) as review_seals,
    ):
        result = check_contract_integrity(
            [{"input_path": "page.png"}],
            seal_candidates=None,
        )

    review_text.assert_called_once()
    review_seals.assert_not_called()
    assert result.page_texts == text_result.page_texts


def test_cross_page_seal_service_normalizes_then_reviews() -> None:
    reviewed = CPSealResult(status="present")
    with (
        patch(
            "core.application.contracts.cross_page_seal_services.normalize_document_images",
            return_value=[],
        ) as normalize,
        patch(
            "core.application.contracts.cross_page_seal_services.review_cross_page_seal_images",
            return_value=reviewed,
        ) as review,
    ):
        result = check_cpseal_services("contract.jpg")

    normalize.assert_called_once_with("contract.jpg")
    review.assert_called_once_with([])
    assert result is reviewed


def test_validity_service_can_run_without_web_search() -> None:
    basic_info = ContractBasicInfo(seller={"name": "乙方"}, buyer={"name": "甲方"})
    with (
        patch(
            "core.application.contracts.validity_service.extract_contract_basic_info",
            return_value=basic_info,
        ),
        patch(
            "core.application.contracts.validity_service.review_contract_authenticity",
            return_value={
                "basic_info": basic_info.model_dump(),
                "party_searches": [],
                "conclusion": "likely_valid",
            },
        ) as review,
    ):
        result = review_contract_validity(
            contract_text="合同正文",
            search_enabled=False,
        )

    assert result["party_searches"] == []
    assert result["validity_review"]["conclusion"] == "likely_valid"
    assert review.call_args.kwargs["search_enabled"] is False
