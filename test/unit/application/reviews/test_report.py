from __future__ import annotations

from core.application.reviews import ContractReviewService
from core.domain.reviews import ReviewStepRecord
from core.infrastructure.reviews import FileReviewStore


REQUIRED_STEPS = {
    "check_basic_info",
    "check_text_integrity",
    "check_contract_seals",
    "check_cross_page_seal",
    "check_contract_authenticity",
}


def _mark_unneeded_steps_attempted(manifest, *present_steps: str) -> None:
    for step_name in REQUIRED_STEPS - set(present_steps):
        manifest.steps[step_name] = ReviewStepRecord(
            status="skipped",
            error="测试中标记为未执行。",
        )


def test_report_is_generated_from_persisted_results_without_model_call(tmp_path) -> None:
    store = FileReviewStore(tmp_path / "reviews")
    manifest = store.create_or_load(
        contract_fingerprint="contract",
        material_fingerprint="material",
        inputs={},
    )
    basic_path = store.write_result(
        manifest.review_id,
        "results/check_basic_info.json",
        {
            "review_status": "completed",
            "summary": {"mismatched_fields": 1},
        },
    )
    authenticity_path = store.write_result(
        manifest.review_id,
        "results/check_contract_authenticity.json",
        {"conclusion": "likely_valid", "risk_points": []},
    )
    manifest.steps.update(
        {
            "check_basic_info": ReviewStepRecord(
                status="completed",
                result_path=str(
                    basic_path.relative_to(store.review_dir(manifest.review_id))
                ),
                versions={"prompt": "basic-v1"},
            ),
            "check_contract_authenticity": ReviewStepRecord(
                status="completed",
                result_path=str(
                    authenticity_path.relative_to(
                        store.review_dir(manifest.review_id)
                    )
                ),
                versions={"prompt": "auth-v1"},
            ),
        }
    )
    _mark_unneeded_steps_attempted(
        manifest,
        "check_basic_info",
        "check_contract_authenticity",
    )
    store.save(manifest)
    service = ContractReviewService(
        store=store,
        versions={
            "check_basic_info": {"prompt": "basic-v1"},
            "check_contract_authenticity": {"prompt": "auth-v1"},
            "write_review_report": {"template": "report-v1"},
        },
    )

    result = service.write_review_report(manifest.review_id)

    assert result["overall_status"] == "risk"
    assert result["sections"]["check_basic_info"]["status"] == "risk"
    assert result["sections"]["check_contract_authenticity"]["status"] == "passed"
    assert (store.review_dir(manifest.review_id) / result["markdown_path"]).exists()
    assert (store.review_dir(manifest.review_id) / result["json_path"]).exists()


def test_report_cache_is_invalidated_when_source_step_changes(tmp_path) -> None:
    store = FileReviewStore(tmp_path / "reviews")
    manifest = store.create_or_load(
        contract_fingerprint="contract",
        material_fingerprint="material",
        inputs={},
    )
    result_path = store.write_result(
        manifest.review_id,
        "results/check_text_integrity.json",
        {
            "contract_continuity": {"status": "continuous"},
            "contract_completeness": {"status": "complete"},
            "replacement_page": {"status": "not_suspected"},
            "contract_clarity": {"status": "clear"},
        },
    )
    manifest.steps["check_text_integrity"] = ReviewStepRecord(
        status="completed",
        result_path=str(result_path.relative_to(store.review_dir(manifest.review_id))),
        versions={"prompt": "integrity-v1"},
    )
    _mark_unneeded_steps_attempted(manifest, "check_text_integrity")
    store.save(manifest)
    service = ContractReviewService(
        store=store,
        versions={
            "check_text_integrity": {"prompt": "integrity-v1"},
            "write_review_report": {"template": "report-v1"},
        },
    )
    first = service.write_review_report(manifest.review_id)
    second = service.write_review_report(manifest.review_id)
    current_status = service.get_review_status(manifest.review_id)

    changed = store.load(manifest.review_id)
    changed.steps["check_text_integrity"].versions["prompt"] = "integrity-v2"
    store.save(changed)
    stale_status = service.get_review_status(manifest.review_id)
    third = service.write_review_report(manifest.review_id)

    assert first["cached"] is False
    assert second["cached"] is True
    assert current_status["steps"]["write_review_report"]["status"] == "completed"
    assert stale_status["steps"]["write_review_report"]["status"] == "stale"
    assert stale_status["ready_for_report"] is False
    assert third["review_status"] == "blocked"
    assert third["stale_steps"] == ["check_text_integrity"]


def test_report_refuses_to_hide_unattempted_required_steps(tmp_path) -> None:
    store = FileReviewStore(tmp_path / "reviews")
    manifest = store.create_or_load(
        contract_fingerprint="contract",
        material_fingerprint="material",
        inputs={},
    )
    service = ContractReviewService(store=store)

    result = service.write_review_report(manifest.review_id)

    status = service.get_review_status(manifest.review_id)
    assert result["review_status"] == "blocked"
    assert set(result["missing_steps"]) == REQUIRED_STEPS
    assert set(status["missing_steps"]) == REQUIRED_STEPS
    assert status["ready_for_report"] is False
