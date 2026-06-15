from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.application.reviews.service import ContractReviewService
from core.application.reviews.versions import build_default_capability_versions
from core.domain.reviews import ReviewManifest, ReviewStepRecord
from core.infrastructure.reviews.file_store import FileReviewStore


# ---------------------------------------------------------------------------
# Helper: build a manifest + all five required step results on disk so
# write_review_report can proceed to the operation phase.
# ---------------------------------------------------------------------------

REQUIRED_STEPS = (
    "check_basic_info",
    "check_text_integrity",
    "check_contract_seals",
    "check_cross_page_seal",
    "check_contract_authenticity",
)

SAMPLE_RESULTS: dict[str, dict] = {
    "check_basic_info": {
        "review_status": "completed",
        "contract_basic_info": {"party_a": "甲公司", "party_b": "乙公司"},
        "compare_result": {},
        "summary": {"mismatched_fields": 0},
    },
    "check_text_integrity": {
        "contract_continuity": {"status": "continuous"},
        "contract_completeness": {"status": "complete"},
        "replacement_page": {"status": "none"},
        "contract_clarity": {"status": "clear"},
    },
    "check_contract_seals": {
        "seller_seal": {"present": True, "status": "intact"},
        "buyer_seal": {"present": True, "status": "intact"},
    },
    "check_cross_page_seal": {
        "status": "intact",
    },
    "check_contract_authenticity": {
        "conclusion": "likely_valid",
    },
}


def _bootstrap_review(
    store: FileReviewStore,
    review_id: str,
    *,
    steps: dict[str, ReviewStepRecord] | None = None,
    write_results: bool = True,
) -> ReviewManifest:
    """Create a review directory + manifest, optionally with step results on disk."""
    review_dir = store.review_dir(review_id)
    review_dir.mkdir(parents=True, exist_ok=True)

    manifest = ReviewManifest(
        review_id=review_id,
        contract_fingerprint="cfp-0001",
        material_fingerprint="mfp-0001",
        inputs={"contract_path": "D:/fake/contract.pdf"},
        steps=steps or {},
    )
    # Let save() create the sub-directories + manifest.json
    store.save(manifest)

    if write_results:
        for step_name, payload in SAMPLE_RESULTS.items():
            store.write_result(
                review_id,
                f"results/{step_name}.json",
                payload,
            )

    return store.load(review_id)


def _build_completed_steps() -> dict[str, ReviewStepRecord]:
    return {
        name: ReviewStepRecord(
            status="completed",
            result_path=f"results/{name}.json",
        )
        for name in REQUIRED_STEPS
    }


# ===================================================================
# Tests
# ===================================================================


class TestWriteReviewReportHappyPath:
    """Verify write_review_report produces JSON + Markdown output on disk."""

    def test_all_steps_passed_produces_report_files(self, tmp_path: Path) -> None:
        store = FileReviewStore(tmp_path / "reviews")
        service = ContractReviewService(store=store, versions={})

        review_id = "review_happy_000001"
        steps = _build_completed_steps()
        _bootstrap_review(store, review_id, steps=steps, write_results=True)

        result = service.write_review_report(review_id)

        # ---- return value ----
        assert result["overall_status"] == "passed"
        assert set(result["sections"].keys()) == set(REQUIRED_STEPS)
        assert result["json_path"] == "reports/contract_review.json"
        assert result["markdown_path"] == "reports/contract_review.md"

        # ---- disk: JSON report ----
        json_path = store.review_dir(review_id) / result["json_path"]
        assert json_path.exists(), f"JSON report missing: {json_path}"
        on_disk_json = json.loads(json_path.read_text(encoding="utf-8"))
        assert on_disk_json["overall_status"] == "passed"

        # ---- disk: Markdown report ----
        md_path = store.review_dir(review_id) / result["markdown_path"]
        assert md_path.exists(), f"Markdown report missing: {md_path}"
        md_content = md_path.read_text(encoding="utf-8")
        assert "# 合同审核报告" in md_content
        assert review_id in md_content
        # Each step should have a heading
        for step_name in REQUIRED_STEPS:
            assert step_name in md_content

    def test_all_steps_passed_is_idempotent(self, tmp_path: Path) -> None:
        """Second call should return cached=True without rewriting."""
        store = FileReviewStore(tmp_path / "reviews")
        service = ContractReviewService(store=store, versions={})

        review_id = "review_idempotent"
        steps = _build_completed_steps()
        _bootstrap_review(store, review_id, steps=steps, write_results=True)

        first = service.write_review_report(review_id)
        assert first.get("cached") is False

        second = service.write_review_report(review_id)
        assert second.get("cached") is True
        assert second["overall_status"] == "passed"


class TestWriteReviewReportBlocked:
    """When required steps are missing or stale, report is blocked — no crash."""

    def test_missing_steps_returns_blocked(self, tmp_path: Path) -> None:
        store = FileReviewStore(tmp_path / "reviews")
        service = ContractReviewService(store=store, versions={})

        review_id = "review_missing_01"
        # Only 1 of 5 steps present
        steps = {
            "check_basic_info": ReviewStepRecord(
                status="completed",
                result_path="results/check_basic_info.json",
            ),
        }
        _bootstrap_review(store, review_id, steps=steps, write_results=False)

        result = service.write_review_report(review_id)

        assert result["review_status"] == "blocked"
        assert len(result["missing_steps"]) == 4
        assert "check_text_integrity" in result["missing_steps"]
        # No sections returned
        assert "sections" not in result

    def test_no_steps_at_all_is_blocked(self, tmp_path: Path) -> None:
        store = FileReviewStore(tmp_path / "reviews")
        service = ContractReviewService(store=store, versions={})

        review_id = "review_empty_01"
        _bootstrap_review(store, review_id, steps={}, write_results=False)

        result = service.write_review_report(review_id)

        assert result["review_status"] == "blocked"
        assert len(result["missing_steps"]) == len(REQUIRED_STEPS)


# ===================================================================
# [WinError 2] / FileNotFoundError risk tests
# ===================================================================


class TestWriteReviewReportFileNotFound:
    """Focus: verify whether [WinError 2] surfaces when files are missing."""

    def test_nonexistent_review_id_raises_file_not_found_error(
        self, tmp_path: Path
    ) -> None:
        """Primary [WinError 2] hotspot.

        ``write_review_report`` calls ``store.load(review_id)`` at the very
        beginning, *before* entering ``run_step`` whose try/except would
        otherwise catch the exception.  ``FileReviewStore.load`` does NOT check
        for existence before calling ``Path.read_text()``, so a non-existent
        review directory or manifest triggers a ``FileNotFoundError`` whose
        underlying OS error on Windows is ``[WinError 2] 系统找不到指定的文件。``
        """
        store = FileReviewStore(tmp_path / "reviews")
        service = ContractReviewService(store=store, versions={})

        with pytest.raises(FileNotFoundError) as exc_info:
            service.write_review_report("review_does_not_exist")

        # On Windows the OS-level error should be WinError 2
        err_msg = str(exc_info.value)
        # pathlib wraps the OS error; the message includes the path
        assert "review_does_not_exist" in err_msg or "review_does_not_exist" in str(
            exc_info.value
        )

    def test_manifest_exists_but_result_file_missing_is_caught_by_run_step(
        self, tmp_path: Path
    ) -> None:
        """If a result file referenced by a completed step is missing from disk,
        the error happens *inside* the ``operation()`` lambda which is guarded
        by ``run_step``'s try/except, so it should NOT surface as a raw
        [WinError 2] but rather be caught and returned as
        ``review_status: execution_failed``.
        """
        store = FileReviewStore(tmp_path / "reviews")
        service = ContractReviewService(store=store, versions={})

        review_id = "review_missing_result"
        # Claim all steps are completed …
        steps = {
            name: ReviewStepRecord(
                status="completed",
                result_path=f"results/{name}.json",
            )
            for name in REQUIRED_STEPS
        }
        # … but do NOT write the actual result files to disk
        _bootstrap_review(store, review_id, steps=steps, write_results=False)

        result = service.write_review_report(review_id)

        # Should be caught gracefully — NOT a raw FileNotFoundError
        assert result["review_status"] == "execution_failed"
        assert "error" in result


# ===================================================================
# Tool-layer (thin wrapper) tests
# ===================================================================


class TestWriteReviewReportTool:
    """Verify the @tool-decorated function in tools.py delegates correctly."""

    def test_tool_invoke_delegates_to_service(self) -> None:
        from unittest.mock import Mock, patch

        from core.application.agent.tools import write_review_report

        service = Mock()
        service.write_review_report.return_value = {
            "overall_status": "passed",
            "sections": {},
            "json_path": "reports/contract_review.json",
            "markdown_path": "reports/contract_review.md",
        }

        with patch(
            "core.application.agent.tools.get_contract_review_service",
            return_value=service,
        ):
            payload = json.loads(
                write_review_report.invoke({"review_id": "review_abc"})
            )

        assert payload["overall_status"] == "passed"
        service.write_review_report.assert_called_once_with("review_abc")

    def test_tool_accepts_only_review_id_argument(self) -> None:
        """write_review_report tool schema should require exactly review_id."""
        from core.application.agent.tools import write_review_report

        schema = write_review_report.args_schema.model_json_schema()
        props = schema.get("properties", {})
        required = schema.get("required", [])

        assert "review_id" in props
        assert props["review_id"]["type"] == "string"
        assert required == ["review_id"]


# ===================================================================
# versions integration: verify that version changes invalidate cache
# ===================================================================


class TestWriteReviewReportVersionAwareness:
    def test_changed_versions_make_report_non_cached(self, tmp_path: Path) -> None:
        """When step versions differ from required, report is regenerated."""
        store = FileReviewStore(tmp_path / "reviews")
        # Use non-empty versions so mismatches matter
        service = ContractReviewService(
            store=store,
            versions={
                "check_basic_info": {"model": "qwen-v1"},
            },
        )

        review_id = "review_versions_01"
        steps = _build_completed_steps()
        # But give check_basic_info a *different* version than required
        steps["check_basic_info"] = ReviewStepRecord(
            status="completed",
            result_path="results/check_basic_info.json",
            versions={"model": "qwen-v0"},  # stale — doesn't match qwen-v1
        )
        _bootstrap_review(store, review_id, steps=steps, write_results=True)

        result = service.write_review_report(review_id)

        # The stale step should block the report
        assert result["review_status"] == "blocked"
        assert "check_basic_info" in result["stale_steps"]


# ===================================================================
# Report content classification
# ===================================================================


class TestWriteReviewReportClassification:
    """Verify overall_status aggregation logic."""

    def test_any_risk_step_yields_overall_risk(self, tmp_path: Path) -> None:
        store = FileReviewStore(tmp_path / "reviews")
        service = ContractReviewService(store=store, versions={})

        review_id = "review_risk_01"
        steps = _build_completed_steps()
        _bootstrap_review(store, review_id, steps=steps, write_results=True)

        # Override one result to indicate risk
        store.write_result(
            review_id,
            "results/check_contract_seals.json",
            {
                "seller_seal": {"present": False, "status": "missing"},
                "buyer_seal": {"present": True, "status": "intact"},
            },
        )

        result = service.write_review_report(review_id)
        assert result["overall_status"] == "risk"

    def test_failed_step_yields_overall_unknown(self, tmp_path: Path) -> None:
        store = FileReviewStore(tmp_path / "reviews")
        service = ContractReviewService(store=store, versions={})

        review_id = "review_failed_01"
        steps = _build_completed_steps()
        # Make one step as failed
        steps["check_contract_authenticity"] = ReviewStepRecord(
            status="failed",
            error="AI model timeout",
        )
        _bootstrap_review(store, review_id, steps=steps, write_results=True)

        result = service.write_review_report(review_id)
        # failed steps → status "execution_failed" → overall becomes "unknown"
        assert result["overall_status"] == "unknown"
