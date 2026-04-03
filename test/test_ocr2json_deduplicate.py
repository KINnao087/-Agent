from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.path_utils import ensure_directory
from core.text import linearize_ocr_page, parse_path_to_json_list, pdf2png
from core.text.ocr2json import deduplicate_ocrjson

TEST_PDF_PATH = ROOT_DIR / "test" / "testfiles" / "contract" / "contract1.pdf"
OUTPUT_ROOT = ROOT_DIR / "test" / "output" / "ocr2json_deduplicate"


def _load_contract_ocrjson() -> list[dict]:
    if not TEST_PDF_PATH.exists():
        raise FileNotFoundError(f"测试 PDF 不存在: {TEST_PDF_PATH}")

    output_dir = ensure_directory(OUTPUT_ROOT)
    png_dir = output_dir / "rendered_pages"

    print(f"测试 PDF: {TEST_PDF_PATH}")
    print(f"渲染目录: {png_dir}")

    image_paths = pdf2png(TEST_PDF_PATH, png_dir, dpi=200)
    contract_pages = parse_path_to_json_list(png_dir)

    ocr_output_path = output_dir / "contract1_ocr_result.json"
    ocr_output_path.write_text(
        json.dumps(contract_pages, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"PDF 渲染页数: {len(image_paths)}")
    print(f"OCR JSON 页数: {len(contract_pages)}")
    print(f"OCR JSON 输出: {ocr_output_path}")

    if len(contract_pages) < 5:
        raise ValueError("contract1.pdf 页数不足，无法覆盖去重测试场景")

    return contract_pages


def _page_label(page_ocr: dict) -> str:
    return Path(str(page_ocr.get("input_path", ""))).name


def _page_preview(page_ocr: dict) -> str:
    text = " ".join(linearize_ocr_page(page_ocr).split())
    return text[:60]


def _print_pages(title: str, pages: list[dict]) -> None:
    print(f"\n{title}，页数: {len(pages)}")
    for index, page in enumerate(pages, start=1):
        print(f"{index}. {_page_label(page)} | {_page_preview(page)}")


def _run_case(case_name: str, left: list[dict], right: list[dict]) -> list[dict]:
    print(f"\n===== {case_name} =====")
    _print_pages("输入集合一", left)
    _print_pages("输入集合二", right)

    result = deduplicate_ocrjson(left, right)
    _print_pages("去重结果", result)
    return result


def main() -> None:
    contract_pages = _load_contract_ocrjson()

    case1_left = contract_pages[0:2]
    case1_right = contract_pages[2:4]
    case1_result = _run_case("无交集", case1_left, case1_right)
    assert case1_result == contract_pages[0:4]

    case2_left = contract_pages[0:3]
    case2_right = contract_pages[2:5]
    case2_result = _run_case("有交集", case2_left, case2_right)
    assert case2_result == contract_pages[0:5]

    case3_left = contract_pages[0:4]
    case3_right = contract_pages[1:3]
    case3_result = _run_case("子集", case3_left, case3_right)
    assert case3_result == contract_pages[0:4]

    print("\n去重测试通过。")


if __name__ == "__main__":
    main()
