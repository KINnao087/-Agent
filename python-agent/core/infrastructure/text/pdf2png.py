from __future__ import annotations

from pathlib import Path

import pymupdf

from core.shared.path_utils import ensure_directory, resolve_path


def pdf2png(
    pdf_path: str | Path,
    output_dir: str | Path,
    dpi: int = 300,
) -> list[str]:
    """把 PDF 每页渲染成 PNG，并返回输出图片路径列表。"""
    pdf_file = resolve_path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"pdf file not found: {pdf_file}")
    if not pdf_file.is_file():
        raise ValueError(f"input path is not a file: {pdf_file}")
    if pdf_file.suffix.lower() != ".pdf":
        raise ValueError("only .pdf files are supported")

    output_path = ensure_directory(output_dir)

    scale = dpi / 72.0
    matrix = pymupdf.Matrix(scale, scale)
    image_paths: list[str] = []

    with pymupdf.open(pdf_file) as document:
        for index, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image_path = output_path / f"page-{index:02d}.png"
            pixmap.save(image_path)
            image_paths.append(str(image_path))

    return image_paths
