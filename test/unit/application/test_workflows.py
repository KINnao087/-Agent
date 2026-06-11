from __future__ import annotations

from unittest.mock import patch

from core.application.workflows.basic_info import BASIC_INFO_GRAPH
from core.application.workflows.chat import build_chat_graph
from core.application.workflows.cross_page_seal import CROSS_PAGE_SEAL_GRAPH
from core.application.workflows.documents import PARSE_DOCUMENTS_GRAPH
from core.application.workflows.integrity import INTEGRITY_GRAPH
from core.application.workflows.validity import VALIDITY_GRAPH
from core.domain.contracts import CPSealFragment, CPSealResult
from core.domain.contracts.integrity_models import ContractIntegrityResult
from core.domain.contracts.models import ContractBasicInfo
from core.infrastructure.ai.schemas import ValidityReviewResponse


def test_basic_info_graph_runs_extract_compare_and_summary() -> None:
    extracted = ContractBasicInfo(contract_no="HT-1")
    platform = ContractBasicInfo(contract_no="HT-1")

    with patch(
        "core.application.workflows.basic_info.extract_contract_basic_info",
        return_value=extracted,
    ):
        state = BASIC_INFO_GRAPH.invoke(
            {
                "contract_text": "合同",
                "platform_basic_info": platform,
            }
        )

    assert state["response"].contract_basic_info == extracted
    assert state["response"].summary.matched_fields == 1


def test_parse_documents_graph_carries_ocr_payload_into_ai_node() -> None:
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
            "core.application.workflows.documents.parse_path_to_json_list",
            side_effect=[[], [], []],
        ),
        patch(
            "core.application.workflows.documents.build_linearized_document",
            return_value={},
        ),
        patch(
            "core.application.workflows.documents.structure_ocr_json",
            return_value=structured,
        ) as structure,
    ):
        state = PARSE_DOCUMENTS_GRAPH.invoke({"file_path": "contract.pdf"})

    assert structure.call_args.args[0]["contract"] == []
    assert state["structured_json"] == structured


def test_chat_graph_compiles_with_model_and_tool_nodes() -> None:
    with patch("core.application.workflows.chat.build_chat_model") as model:
        graph = build_chat_graph()

    assert {"assistant", "tools"} <= set(graph.get_graph().nodes)


def test_integrity_graph_runs_text_review_without_seal_review() -> None:
    expected = ContractIntegrityResult()
    with (
        patch(
            "core.application.workflows.integrity.linearize_ocr_page",
            return_value="page text",
        ),
        patch(
            "core.application.workflows.integrity.review_contract_integrity",
            return_value=expected,
        ),
    ):
        state = INTEGRITY_GRAPH.invoke(
            {
                "contract_pages": [{"input_path": "page.png"}],
                "detect_seals": False,
                "review_seals": False,
            }
        )

    assert state["page_texts"][0].page_text == "page text"
    assert state["result"] is expected


def test_cross_page_seal_graph_runs_detection_analysis_and_review(tmp_path) -> None:
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"image")
    fragment = CPSealFragment(
        page_index=1,
        image_path=str(image_path),
        edge="right",
        bbox=[1, 2, 3, 4],
    )
    pre_result = CPSealResult(status="incomplete")
    reviewed = CPSealResult(status="present")
    with (
        patch(
            "core.application.workflows.cross_page_seal.detect_cross_page_seal_fragments",
            return_value=[fragment],
        ),
        patch(
            "core.application.workflows.cross_page_seal.analyze_cross_page_seal_results",
            return_value=pre_result,
        ),
        patch(
            "core.application.workflows.cross_page_seal.review_spseal_results",
            return_value=reviewed,
        ),
    ):
        state = CROSS_PAGE_SEAL_GRAPH.invoke({"input_path": str(image_path)})

    assert state["pre_result"].page_count == 1
    assert state["result"] is reviewed


def test_validity_graph_can_run_without_web_search() -> None:
    basic_info = ContractBasicInfo(seller={"name": "乙方"}, buyer={"name": "甲方"})
    review = ValidityReviewResponse(conclusion="likely_valid")
    with (
        patch(
            "core.application.workflows.validity.extract_contract_basic_info",
            return_value=basic_info,
        ),
        patch(
            "core.application.workflows.validity.invoke_structured",
            return_value=review,
        ),
    ):
        state = VALIDITY_GRAPH.invoke(
            {
                "contract_text": "合同正文",
                "search_enabled": False,
            }
        )

    assert state["party_searches"] == []
    assert state["validity_review"]["conclusion"] == "likely_valid"
