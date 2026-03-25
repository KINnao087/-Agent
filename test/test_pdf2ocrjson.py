from __future__ import annotations

import json
from pathlib import Path

from core.path_utils import ensure_directory
from core.text import parse_path_to_json_list, pdf2png

TEST_ROOT = Path(__file__).resolve().parent / "testfiles"
OUTPUT_ROOT = Path(__file__).resolve().parent / "output" / "pdf2ocrjson"
TEST_PDF_PATH = TEST_ROOT / "contract" / "contract_combined.pdf"


def main() -> None:
    """测试 PDF -> PNG -> OCR JSON 的整条转换链路。"""
    if not TEST_PDF_PATH.exists():
        raise FileNotFoundError(f"测试 PDF 不存在: {TEST_PDF_PATH}")

    output_dir = ensure_directory(OUTPUT_ROOT)
    png_dir = output_dir / "rendered_pages"

    image_paths = pdf2png(TEST_PDF_PATH, png_dir, dpi=200)
    ocr_json_list = parse_path_to_json_list(png_dir)

    assert image_paths, "PDF 转 PNG 没有产出图片"
    assert len(image_paths) == len(ocr_json_list), "PNG 数量与 OCR JSON 数量不一致"
    assert any((item.get("rec_texts") or []) for item in ocr_json_list), "OCR JSON 中没有识别文本"

    ocr_output_path = output_dir / "ocr_result.json"
    ocr_output_path.write_text(
        json.dumps(ocr_json_list, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"test_pdf={TEST_PDF_PATH}")
    print(f"png_pages={len(image_paths)}")
    print(f"ocr_json_pages={len(ocr_json_list)}")
    print(f"rendered_dir={png_dir}")
    print(f"ocr_json_output={ocr_output_path}")


if __name__ == "__main__":
    main()
