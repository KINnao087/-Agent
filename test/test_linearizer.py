from __future__ import annotations

from pathlib import Path

from core.text import (
    build_linearized_document,
    parse_path_to_json_list,
    write_linearized_outputs,
)

TEST_ROOT = Path(__file__).resolve().parent / "testfiles"
OUTPUT_ROOT = Path(__file__).resolve().parent / "output"


def build_test_payload() -> dict:
    """构造线性化测试用的 OCR 输入对象。"""
    return {
        "input_path": str((TEST_ROOT / "contract").resolve()),
        "contract": parse_path_to_json_list(TEST_ROOT / "contract"),
        "attachments": parse_path_to_json_list(TEST_ROOT / "attachments"),
        "invoice": parse_path_to_json_list(TEST_ROOT / "invoice"),
    }


def main() -> None:
    """执行线性化测试并把合同、附件、发票分别写入文件。"""
    payload = build_test_payload()
    linearized = build_linearized_document(payload)

    # 至少要生成合同正文线性化结果。
    assert payload["contract"], "合同 OCR 结果不能为空"
    assert linearized["contract_texts"], "合同线性化文本不能为空"
    assert linearized["full_text"], "完整线性化文档不能为空"

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    output_paths = write_linearized_outputs(linearized, OUTPUT_ROOT)

    assert Path(output_paths["contract"]).exists(), "合同线性化输出文件不存在"
    assert Path(output_paths["attachments"]).exists(), "附件线性化输出文件不存在"
    assert Path(output_paths["invoice"]).exists(), "发票线性化输出文件不存在"

    print(f"contract_pages={len(payload['contract'])}")
    print(f"attachment_pages={len(payload['attachments'])}")
    print(f"invoice_pages={len(payload['invoice'])}")
    print(f"contract_text_chars={len(linearized['contract_text'])}")
    print(f"attachments_text_chars={len(linearized['attachment_text'])}")
    print(f"invoice_text_chars={len(linearized['invoice_text'])}")
    print(f"contract_linearized={output_paths['contract']}")
    print(f"attachments_linearized={output_paths['attachments']}")
    print(f"invoice_linearized={output_paths['invoice']}")


if __name__ == "__main__":
    main()
