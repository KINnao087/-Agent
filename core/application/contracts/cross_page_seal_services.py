from pathlib import Path

from core.domain.contracts import CPSealResult
from core.infrastructure.text import pdf2png
from core.infrastructure.vision.seal.cross_page_detector import detect_cross_page_seal_fragments, \
    analyze_cross_page_seal_results

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def _collect_page_images(input_path: str | Path) -> list[Path]:
    path = Path(input_path)

    if not path.exists():
        raise FileNotFoundError(path)

    if path.is_file() and path.suffix.lower() == ".pdf":
        output_dir = path.parent / "_pdf_pages" / path.stem
        return [Path(item) for item in pdf2png(path, output_dir)]

    if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
        return [path]

    if path.is_dir():
        return sorted(
            item
            for item in path.iterdir()
            if item.is_file() and item.suffix.lower() in IMAGE_SUFFIXES
        )

    raise ValueError(f"unsupported input path: {path}")

def check_cpseal_services(input_dir: Path) -> CPSealResult:
    image_paths = _collect_page_images(input_dir)
    fragments = []
    for i, image_path in enumerate(image_paths, start=1):
        fragments.extend(detect_cross_page_seal_fragments(
            image_path = image_path,
            page_index = i,
        ))

    res = analyze_cross_page_seal_results(fragments)
    res.page_count = len(fragments)
    return res
