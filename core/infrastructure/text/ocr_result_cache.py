from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from .paddle_ocr import get_paddle_ocr, predict_ocr_image

PROJECT_ROOT = Path(__file__).resolve().parents[3]
# Bump this namespace whenever the OCR model or inference settings change.
OCR_CACHE_NAMESPACE = "ppocrv5-server-ch-v1"
DEFAULT_OCR_CACHE_DIR = (
    PROJECT_ROOT / "artifacts" / "cache" / "ocr" / OCR_CACHE_NAMESPACE
)
_cache_locks = [Lock() for _ in range(64)]


def get_ocr_cache_dir(cache_dir: str | Path | None = None) -> Path:
    configured = cache_dir or os.getenv("OCR_RESULT_CACHE_DIR")
    path = Path(configured) if configured else DEFAULT_OCR_CACHE_DIR
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def image_sha256(image_path: str | Path) -> str:
    return hashlib.sha256(Path(image_path).read_bytes()).hexdigest()


def _read_cached_result(cache_path: Path, image_path: Path) -> dict[str, Any]:
    result = json.loads(cache_path.read_text(encoding="utf-8"))
    result["input_path"] = str(image_path)
    return result


def _write_cached_result(cache_path: Path, result: dict[str, Any]) -> None:
    temporary_path = cache_path.with_name(
        f".{cache_path.name}.{uuid4().hex}.tmp"
    )
    temporary_path.write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary_path.replace(cache_path)


def get_or_predict_ocr(
    image_path: str | Path,
    *,
    device: str = "gpu",
    cache_dir: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(image_path).resolve()
    cache_root = get_ocr_cache_dir(cache_dir)
    key = image_sha256(path)
    cache_path = cache_root / f"{key}.json"

    if cache_path.is_file():
        return _read_cached_result(cache_path, path)

    cache_lock = _cache_locks[int(key[:8], 16) % len(_cache_locks)]
    with cache_lock:
        if cache_path.is_file():
            return _read_cached_result(cache_path, path)

        result = predict_ocr_image(get_paddle_ocr(device), str(path))
        cache_root.mkdir(parents=True, exist_ok=True)
        _write_cached_result(cache_path, result)
        return result
