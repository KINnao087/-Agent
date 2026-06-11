from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

from core.shared.path_utils import ensure_directory, resolve_path

from .pdf2png import pdf2png

SUPPORTED_DOCUMENT_SUFFIXES = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".webp",
}


def _output_root(path: Path, output_dir: str | Path | None) -> Path:
    if output_dir:
        return resolve_path(output_dir)
    parent = path if path.is_dir() else path.parent
    return parent / "_normalized_images"


def _image_to_png(image_path: Path, output_dir: Path) -> Path:
    target_dir = ensure_directory(
        output_dir / f"{image_path.stem}_{image_path.suffix.lower()[1:]}"
    )
    target_path = target_dir / f"{image_path.stem}.png"
    with Image.open(image_path) as image:
        ImageOps.exif_transpose(image).convert("RGB").save(target_path, format="PNG")
    return target_path


def _normalize_file(file_path: Path, output_dir: Path, dpi: int) -> list[Path]:
    suffix = file_path.suffix.lower()
    if suffix == ".png":
        return [file_path]
    if suffix in SUPPORTED_DOCUMENT_SUFFIXES - {".pdf", ".png"}:
        return [_image_to_png(file_path, output_dir)]
    if suffix == ".pdf":
        rendered_dir = output_dir / f"{file_path.stem}_pdf"
        return [Path(path) for path in pdf2png(file_path, rendered_dir, dpi=dpi)]
    raise ValueError(f"unsupported document type: {file_path.suffix}")


def normalize_document_images(
    input_path: str | Path,
    output_dir: str | Path | None = None,
    dpi: int = 300,
) -> list[Path]:
    """Normalize a PDF, raster image, or image directory into ordered PNG paths."""
    path = resolve_path(input_path)
    if not path.exists():
        raise FileNotFoundError(path)

    normalized_root = _output_root(path, output_dir)
    if path.is_file():
        return _normalize_file(path, normalized_root, dpi)
    if not path.is_dir():
        raise ValueError(f"unsupported input path: {path}")

    source_files = sorted(
        item
        for item in path.iterdir()
        if item.is_file() and item.suffix.lower() in SUPPORTED_DOCUMENT_SUFFIXES
    )
    return [
        image_path
        for source_file in source_files
        for image_path in _normalize_file(source_file, normalized_root, dpi)
    ]
