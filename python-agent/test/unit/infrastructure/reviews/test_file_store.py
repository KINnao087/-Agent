from __future__ import annotations

import json

from core.domain.reviews import ReviewStepRecord
from core.infrastructure.reviews import (
    FileReviewStore,
    build_material_fingerprint,
    fingerprint_page_set,
    is_step_current,
)


def test_page_set_fingerprint_is_content_based_and_order_sensitive(tmp_path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    renamed = tmp_path / "renamed.png"
    first.write_bytes(b"page-one")
    second.write_bytes(b"page-two")
    renamed.write_bytes(b"page-one")

    original = fingerprint_page_set([first, second])
    same_content = fingerprint_page_set([renamed, second])
    reversed_pages = fingerprint_page_set([second, first])

    assert same_content == original
    assert reversed_pages != original


def test_material_fingerprint_tracks_supporting_material_and_platform_data(tmp_path) -> None:
    contract = tmp_path / "contract.png"
    attachment = tmp_path / "attachment.png"
    contract.write_bytes(b"contract")
    attachment.write_bytes(b"attachment")
    contract_fingerprint = fingerprint_page_set([contract])

    base = build_material_fingerprint(
        contract_fingerprint=contract_fingerprint,
        attachment_paths=[attachment],
        invoice_paths=[],
        platform_data={"amount": "100", "name": "A"},
    )
    reordered_platform = build_material_fingerprint(
        contract_fingerprint=contract_fingerprint,
        attachment_paths=[attachment],
        invoice_paths=[],
        platform_data={"name": "A", "amount": "100"},
    )
    changed_platform = build_material_fingerprint(
        contract_fingerprint=contract_fingerprint,
        attachment_paths=[attachment],
        invoice_paths=[],
        platform_data={"amount": "200", "name": "A"},
    )

    assert reordered_platform == base
    assert changed_platform != base


def test_store_reuses_review_for_same_material_and_restores_step_state(tmp_path) -> None:
    store = FileReviewStore(tmp_path / "reviews")
    first = store.create_or_load(
        contract_fingerprint="contract-hash",
        material_fingerprint="material-hash",
        inputs={"contract_path": "D:/contracts/a.pdf"},
    )
    first.steps["prepare_contract"] = ReviewStepRecord(
        status="completed",
        result_path="results/prepare_contract.json",
        versions={"ocr": "ocr-v1"},
    )
    store.save(first)

    loaded = store.create_or_load(
        contract_fingerprint="contract-hash",
        material_fingerprint="material-hash",
        inputs={"contract_path": "D:/renamed/a.pdf"},
    )

    assert loaded.review_id == first.review_id
    assert loaded.steps["prepare_contract"].status == "completed"
    persisted = json.loads(store.manifest_path(first.review_id).read_text(encoding="utf-8"))
    assert persisted["review_id"] == first.review_id


def test_step_version_validation_is_selective() -> None:
    record = ReviewStepRecord(
        status="completed",
        versions={"model": "qwen-a", "prompt": "seal-v1", "detector": "hybrid-v2"},
    )

    assert is_step_current(
        record,
        {"model": "qwen-a", "prompt": "seal-v1", "detector": "hybrid-v2"},
    )
    assert not is_step_current(
        record,
        {"model": "qwen-a", "prompt": "seal-v2", "detector": "hybrid-v2"},
    )
    assert not is_step_current(
        ReviewStepRecord(status="failed", versions=record.versions),
        record.versions,
    )
