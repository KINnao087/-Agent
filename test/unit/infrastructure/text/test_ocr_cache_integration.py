from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from core.infrastructure.text.ocr2json import parse_file_to_json


def test_parse_file_reuses_cached_ocr_instance(tmp_path: Path) -> None:
    image_path = tmp_path / "page.png"
    image_path.touch()
    ocr = object()

    with (
        patch(
            "core.infrastructure.text.ocr2json.get_paddle_ocr",
            return_value=ocr,
        ) as get_ocr,
        patch(
            "core.infrastructure.text.ocr2json.predict_ocr_image",
            return_value={"rec_texts": ["contract"]},
        ) as predict,
    ):
        first = parse_file_to_json(image_path)
        second = parse_file_to_json(image_path)

    assert first == second == {"rec_texts": ["contract"]}
    assert get_ocr.call_count == 2
    assert predict.call_count == 2
    assert all(call.args[0] is ocr for call in predict.call_args_list)
