from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def _json_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_hash(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint_page_set(paths: Iterable[str | Path]) -> str:
    return _json_hash(
        [
            {"page_index": index, "sha256": _file_hash(path)}
            for index, path in enumerate(paths, start=1)
        ]
    )


def build_material_fingerprint(
    *,
    contract_fingerprint: str,
    attachment_paths: Iterable[str | Path] = (),
    invoice_paths: Iterable[str | Path] = (),
    platform_data: dict[str, Any] | None = None,
) -> str:
    return _json_hash(
        {
            "contract": contract_fingerprint,
            "attachments": [
                {"index": index, "sha256": _file_hash(path)}
                for index, path in enumerate(attachment_paths, start=1)
            ],
            "invoices": [
                {"index": index, "sha256": _file_hash(path)}
                for index, path in enumerate(invoice_paths, start=1)
            ],
            "platform_data": platform_data or {},
        }
    )
