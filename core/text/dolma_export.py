from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now_iso() -> str:
    """生成 UTC 时间戳字符串。"""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _build_record_id(group_id: str, role: str) -> str:
    """根据输入组和文档角色生成稳定的记录 ID。"""
    digest = hashlib.sha1(f"{group_id}:{role}".encode("utf-8")).hexdigest()[:12]
    return f"{group_id}-{role}-{digest}"


def _build_single_record(
    *,
    group_id: str,
    role: str,
    text: str,
    input_path: str,
    page_count: int,
    timestamp: str,
    source: str,
    structured_doc: dict,
) -> dict:
    """构造单条 Dolma 风格记录。"""
    return {
        "id": _build_record_id(group_id, role),
        "text": text,
        "source": source,
        "created": timestamp,
        "added": timestamp,
        "metadata": {
            "group_id": group_id,
            "role": role,
            "file_name": Path(input_path).name,
            "input_path": input_path,
            "page_count": page_count,
            "structured": structured_doc if role == "contract" else {},
        },
    }


def build_dolma_records(
    ocr_payload: dict,
    linearized_doc: dict,
    structured_doc: dict,
    source: str = "tech_contract",
) -> list[dict]:
    """把线性化文档和结构化结果组装成 Dolma 风格记录列表。"""
    input_path = str(ocr_payload.get("input_path", "document"))
    group_id = Path(input_path).name or "document"
    timestamp = _utc_now_iso()

    candidates = [
        ("contract", linearized_doc.get("contract_text", ""), len(ocr_payload.get("contract", []))),
        ("attachments", linearized_doc.get("attachment_text", ""), len(ocr_payload.get("attachments", []))),
        ("invoice", linearized_doc.get("invoice_text", ""), len(ocr_payload.get("invoice", []))),
    ]

    records: list[dict] = []
    for role, text, page_count in candidates:
        if not text:
            continue
        records.append(
            _build_single_record(
                group_id=group_id,
                role=role,
                text=text,
                input_path=input_path,
                page_count=page_count,
                timestamp=timestamp,
                source=source,
                structured_doc=structured_doc,
            )
        )
    return records


def write_jsonl(records: list[dict], output_path: str | Path) -> str:
    """把记录列表写成 JSONL 文件。"""
    path = Path(output_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return str(path)
