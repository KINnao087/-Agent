from __future__ import annotations

from typing import Any

from core.infrastructure.text import (
    build_linearized_document,
    parse_path_to_json_list,
)
from core.shared.path_utils import resolve_path


def load_document_payload(
    file_path: str,
    attachments_path: str | None = None,
    invoice_path: str | None = None,
) -> dict[str, Any]:
    payload = {
        "input_path": str(resolve_path(file_path)),
        "contract": parse_path_to_json_list(file_path),
        "attachments": parse_path_to_json_list(attachments_path),
        "invoice": parse_path_to_json_list(invoice_path),
    }
    payload["linearized"] = build_linearized_document(payload)
    return payload
