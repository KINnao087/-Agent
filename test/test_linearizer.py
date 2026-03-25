from __future__ import annotations

from pathlib import Path

from core.text import build_linearized_document, parse_path_to_json_list

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
    """执行线性化测试并输出结果文件。"""
    payload = build_test_payload()
    linearized = build_linearized_document(payload)

    # 这些断言用于确认线性化流程至少产出了主合同文本。
    assert payload["contract"], "合同 OCR 结果不能为空"
    assert linearized["contract_texts"], "合同线性化文本不能为空"
    assert linearized["full_text"], "完整线性化文档不能为空"

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_ROOT / "linearized_document.txt"
    output_path.write_text(linearized["full_text"], encoding="utf-8")

    print(f"contract_pages={len(payload['contract'])}")
    print(f"attachment_pages={len(payload['attachments'])}")
    print(f"invoice_pages={len(payload['invoice'])}")
    print(f"linearized_chars={len(linearized['full_text'])}")
    print(f"saved_to={output_path}")


if __name__ == "__main__":
    main()
