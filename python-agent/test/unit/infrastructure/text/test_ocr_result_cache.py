from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from core.infrastructure.text.ocr_result_cache import (
    get_or_predict_ocr,
    image_sha256,
)


def test_cache_miss_runs_ocr_and_writes_hash_key(tmp_path: Path) -> None:
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"image-content")
    cache_dir = tmp_path / "cache"
    expected = {
        "input_path": str(image_path.resolve()),
        "rec_texts": ["contract"],
        "rec_boxes": [],
        "rec_scores": [],
    }

    with (
        patch(
            "core.infrastructure.text.ocr_result_cache.get_paddle_ocr",
            return_value=object(),
        ),
        patch(
            "core.infrastructure.text.ocr_result_cache.predict_ocr_image",
            return_value=expected,
        ) as predict,
    ):
        result = get_or_predict_ocr(image_path, cache_dir=cache_dir)

    key = hashlib.sha256(b"image-content").hexdigest()
    assert result == expected
    assert json.loads((cache_dir / f"{key}.json").read_text("utf-8")) == expected
    predict.assert_called_once()


def test_cache_hit_skips_ocr_and_updates_input_path(tmp_path: Path) -> None:
    first_path = tmp_path / "first.png"
    second_path = tmp_path / "second.png"
    first_path.write_bytes(b"same-image")
    second_path.write_bytes(b"same-image")
    cache_dir = tmp_path / "cache"
    cached = {
        "input_path": str(first_path.resolve()),
        "rec_texts": ["cached"],
        "rec_boxes": [],
        "rec_scores": [],
    }

    with (
        patch(
            "core.infrastructure.text.ocr_result_cache.get_paddle_ocr",
            return_value=object(),
        ),
        patch(
            "core.infrastructure.text.ocr_result_cache.predict_ocr_image",
            return_value=cached,
        ) as predict,
    ):
        get_or_predict_ocr(first_path, cache_dir=cache_dir)
        result = get_or_predict_ocr(second_path, cache_dir=cache_dir)

    assert result["input_path"] == str(second_path.resolve())
    assert result["rec_texts"] == ["cached"]
    predict.assert_called_once()


def test_changed_image_content_creates_new_cache_entry(tmp_path: Path) -> None:
    image_path = tmp_path / "page.png"
    cache_dir = tmp_path / "cache"
    image_path.write_bytes(b"version-one")

    with (
        patch(
            "core.infrastructure.text.ocr_result_cache.get_paddle_ocr",
            return_value=object(),
        ),
        patch(
            "core.infrastructure.text.ocr_result_cache.predict_ocr_image",
            side_effect=[
                {"rec_texts": ["one"]},
                {"rec_texts": ["two"]},
            ],
        ) as predict,
    ):
        get_or_predict_ocr(image_path, cache_dir=cache_dir)
        image_path.write_bytes(b"version-two")
        result = get_or_predict_ocr(image_path, cache_dir=cache_dir)

    assert result["rec_texts"] == ["two"]
    assert len(list(cache_dir.glob("*.json"))) == 2
    assert predict.call_count == 2


def test_concurrent_requests_for_same_image_run_ocr_once(tmp_path: Path) -> None:
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"shared-image")
    cache_dir = tmp_path / "cache"

    with (
        patch(
            "core.infrastructure.text.ocr_result_cache.get_paddle_ocr",
            return_value=object(),
        ),
        patch(
            "core.infrastructure.text.ocr_result_cache.predict_ocr_image",
            return_value={"rec_texts": ["shared"]},
        ) as predict,
    ):
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(
                executor.map(
                    lambda _: get_or_predict_ocr(
                        image_path,
                        cache_dir=cache_dir,
                    ),
                    range(8),
                )
            )

    assert all(result["rec_texts"] == ["shared"] for result in results)
    predict.assert_called_once()


def test_image_sha256_reads_binary_content(tmp_path: Path) -> None:
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"\x00\xff\x10")

    assert image_sha256(image_path) == hashlib.sha256(b"\x00\xff\x10").hexdigest()
