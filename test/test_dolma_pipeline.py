from __future__ import annotations

import json
from pathlib import Path

from core.ai import structure_ocr_json
from core.text import (
    build_dolma_records,
    build_linearized_document,
    parse_path_to_json_list,
    write_jsonl,
    write_linearized_outputs,
)

TEST_ROOT = Path(__file__).resolve().parent / "testfiles"
OUTPUT_ROOT = Path(__file__).resolve().parent / "output"


def build_test_payload() -> dict:
    """构造整流程测试用的 OCR 输入对象。"""
    return {
        "input_path": str((TEST_ROOT / "contract").resolve()),
        "contract": parse_path_to_json_list(TEST_ROOT / "contract"),
        "attachments": parse_path_to_json_list(TEST_ROOT / "attachments"),
        "invoice": parse_path_to_json_list(TEST_ROOT / "invoice"),
    }


def main() -> None:
    """执行线性化、结构化解析和 Dolma 导出整流程测试。"""
    payload = build_test_payload()
    linearized = build_linearized_document(payload)
    payload["linearized"] = linearized

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    linearized_paths = write_linearized_outputs(linearized, OUTPUT_ROOT)

    # 线性化阶段至少要有合同正文输出。
    assert payload["contract"], "合同 OCR 结果不能为空"
    assert linearized["contract_text"], "合同线性化文本不能为空"

    structured = structure_ocr_json(payload)
    structured_path = OUTPUT_ROOT / "structured_result.json"
    structured_path.write_text(
        json.dumps(structured, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    records = build_dolma_records(payload, linearized, structured)
    assert records, "Dolma 记录不能为空"
    assert any(record["metadata"]["role"] == "contract" for record in records), "缺少合同 Dolma 记录"

    if payload["attachments"]:
        assert any(
            record["metadata"]["role"] == "attachments" for record in records
        ), "缺少附件 Dolma 记录"
    if payload["invoice"]:
        assert any(
            record["metadata"]["role"] == "invoice" for record in records
        ), "缺少发票 Dolma 记录"

    jsonl_path = write_jsonl(records, OUTPUT_ROOT / "dolma_records.jsonl")

    assert Path(linearized_paths["contract"]).exists(), "合同线性化输出文件不存在"
    assert Path(linearized_paths["attachments"]).exists(), "附件线性化输出文件不存在"
    assert Path(linearized_paths["invoice"]).exists(), "发票线性化输出文件不存在"
    assert structured_path.exists(), "结构化 JSON 输出文件不存在"
    assert Path(jsonl_path).exists(), "Dolma JSONL 输出文件不存在"

    print(f"contract_pages={len(payload['contract'])}")
    print(f"attachment_pages={len(payload['attachments'])}")
    print(f"invoice_pages={len(payload['invoice'])}")
    print(f"contract_text_chars={len(linearized['contract_text'])}")
    print(f"attachments_text_chars={len(linearized['attachment_text'])}")
    print(f"invoice_text_chars={len(linearized['invoice_text'])}")
    print(f"dolma_record_count={len(records)}")
    print(f"contract_linearized={linearized_paths['contract']}")
    print(f"attachments_linearized={linearized_paths['attachments']}")
    print(f"invoice_linearized={linearized_paths['invoice']}")
    print(f"structured_json={structured_path}")
    print(f"dolma_jsonl={jsonl_path}")


if __name__ == "__main__":
    main()
