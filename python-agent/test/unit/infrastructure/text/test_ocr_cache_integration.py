from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from core.infrastructure.text.ocr2json import parse_file_to_json


def test_parse_file_uses_ocr_result_cache(tmp_path: Path) -> None:
    image_path = tmp_path / "page.png"
    image_path.touch()

    with patch(
        "core.infrastructure.text.ocr2json.get_or_predict_ocr",
        return_value={"rec_texts": ["contract"]},
    ) as cached_ocr:
        result = parse_file_to_json(image_path)

    assert result == {"rec_texts": ["contract"]}
    cached_ocr.assert_called_once_with(image_path.resolve())
