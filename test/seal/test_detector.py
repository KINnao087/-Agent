from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.text.pdf2png import pdf2png
from core.vision.seal.detector import detect_seal_candidates

DEFAULT_INPUT_PDF = (
    ROOT_DIR
    / "test"
    / "testfiles"
    / "contract"
    / "contract1.pdf"
)
RENDER_DIR = (
    ROOT_DIR
    / "test"
    / "output"
    / "contract1_simulated_tampering_detect"
    / "pages"
)


def main() -> None:
    """读取 PDF，检测签章候选，并打印裁剪结果。"""
    input_pdf = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_INPUT_PDF
    if not input_pdf.exists():
        raise FileNotFoundError(f"pdf not found: {input_pdf}")

    page_paths = [Path(path) for path in pdf2png(input_pdf, RENDER_DIR, dpi=200)]
    print(f"输入 PDF: {input_pdf}")
    print(f"渲染页数: {len(page_paths)}")

    all_candidates = []
    for page_index, page_path in enumerate(page_paths, start=1):
        page_candidates = detect_seal_candidates(image_path=page_path, page_index=page_index)
        all_candidates.extend(page_candidates)

        print(f"\n第 {page_index} 页: {page_path}")
        print(f"候选数量: {len(page_candidates)}")
        for index, candidate in enumerate(page_candidates):
            print(f"[{index}] bbox={candidate.bbox}")
            print(f"    crop={candidate.crop_path}")
            print(f"    enhanced={candidate.enhanced_crop_path}")

    print(f"\n总候选数量: {len(all_candidates)}")


if __name__ == "__main__":
    main()
