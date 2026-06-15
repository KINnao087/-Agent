from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from core.infrastructure.text.ocr2json import parse_path_to_json_list


def test_ocr_path_uses_normalized_png_pages() -> None:
    pages = [Path("page-01.png"), Path("page-02.png")]
    with (
        patch(
            "core.infrastructure.text.ocr2json.normalize_document_images",
            return_value=pages,
        ) as normalize,
        patch(
            "core.infrastructure.text.ocr2json.parse_file_to_json",
            side_effect=[
                {"rec_texts": ["第一页"]},
                {"rec_texts": ["第二页"]},
            ],
        ) as parse,
    ):
        result = parse_path_to_json_list("contract.jpg")

    normalize.assert_called_once_with("contract.jpg")
    assert [call.args[0] for call in parse.call_args_list] == pages
    assert len(result) == 2
