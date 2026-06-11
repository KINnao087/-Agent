from __future__ import annotations

import os
import sys
from threading import Lock
from typing import Any

_ocr_instances: dict[str, Any] = {}
_ocr_instances_lock = Lock()


def _install_paddlex_langchain_compatibility() -> None:
    """Bridge PaddleX imports removed from LangChain 1.x."""
    import langchain_classic.docstore as classic_docstore
    import langchain_classic.docstore.document as classic_document
    import langchain_classic.text_splitter as classic_text_splitter

    sys.modules.setdefault("langchain.docstore", classic_docstore)
    sys.modules.setdefault("langchain.docstore.document", classic_document)
    sys.modules.setdefault("langchain.text_splitter", classic_text_splitter)


def create_paddle_ocr(device: str = "gpu") -> Any:
    os.environ["FLAGS_use_mkldnn"] = "0"
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    _install_paddlex_langchain_compatibility()

    from paddleocr import PaddleOCR

    return PaddleOCR(
        lang="ch",
        device=device,
        enable_mkldnn=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )


def get_paddle_ocr(device: str = "gpu") -> Any:
    instance = _ocr_instances.get(device)
    if instance is not None:
        return instance

    with _ocr_instances_lock:
        instance = _ocr_instances.get(device)
        if instance is None:
            instance = create_paddle_ocr(device)
            _ocr_instances[device] = instance
        return instance


def clear_paddle_ocr_cache() -> None:
    with _ocr_instances_lock:
        _ocr_instances.clear()


def predict_ocr_image(ocr: Any, image_path: str) -> dict:
    results = list(ocr.predict(image_path))
    if not results:
        return {
            "input_path": image_path,
            "rec_texts": [],
            "rec_boxes": [],
            "rec_scores": [],
        }

    result = dict(results[0].json)
    if isinstance(result.get("res"), dict):
        result = dict(result["res"])
    result["input_path"] = image_path
    return result
