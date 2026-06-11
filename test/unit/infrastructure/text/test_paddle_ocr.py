from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from core.infrastructure.text.paddle_ocr import (
    _install_paddlex_langchain_compatibility,
    clear_paddle_ocr_cache,
    get_paddle_ocr,
)


def test_paddlex_langchain_compatibility_aliases_removed_modules() -> None:
    _install_paddlex_langchain_compatibility()

    assert "langchain.docstore" in sys.modules
    assert "langchain.docstore.document" in sys.modules
    assert "langchain.text_splitter" in sys.modules


def test_get_paddle_ocr_lazily_caches_instance() -> None:
    instance = object()
    clear_paddle_ocr_cache()

    with patch(
        "core.infrastructure.text.paddle_ocr.create_paddle_ocr",
        return_value=instance,
    ) as create:
        assert get_paddle_ocr() is instance
        assert get_paddle_ocr() is instance

    create.assert_called_once_with("gpu")
    clear_paddle_ocr_cache()


def test_get_paddle_ocr_creates_one_instance_for_concurrent_calls() -> None:
    instance = object()
    clear_paddle_ocr_cache()

    with patch(
        "core.infrastructure.text.paddle_ocr.create_paddle_ocr",
        return_value=instance,
    ) as create:
        with ThreadPoolExecutor(max_workers=4) as executor:
            instances = list(executor.map(lambda _: get_paddle_ocr(), range(8)))

    assert all(value is instance for value in instances)
    create.assert_called_once_with("gpu")
    clear_paddle_ocr_cache()
