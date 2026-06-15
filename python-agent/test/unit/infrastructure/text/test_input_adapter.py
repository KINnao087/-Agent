from __future__ import annotations

from unittest.mock import patch

from PIL import Image

from core.infrastructure.text.input_adapter import normalize_document_images


def test_png_is_used_without_conversion(tmp_path) -> None:
    image_path = tmp_path / "page.png"
    Image.new("RGB", (4, 4), "white").save(image_path)

    result = normalize_document_images(image_path)

    assert result == [image_path.resolve()]
    assert not (tmp_path / "_normalized_images").exists()


def test_jpg_is_converted_to_png(tmp_path) -> None:
    image_path = tmp_path / "page.jpg"
    Image.new("RGB", (4, 4), "white").save(image_path, format="JPEG")

    result = normalize_document_images(image_path)

    assert len(result) == 1
    assert result[0].suffix == ".png"
    assert result[0].parent.name == "page_jpg"
    with Image.open(result[0]) as image:
        assert image.format == "PNG"


def test_pdf_is_rendered_to_ordered_png_pages(tmp_path) -> None:
    pdf_path = tmp_path / "contract.pdf"
    pdf_path.write_bytes(b"pdf")
    page_paths = [
        tmp_path / "_normalized_images" / "contract_pdf" / "page-01.png",
        tmp_path / "_normalized_images" / "contract_pdf" / "page-02.png",
    ]

    with patch(
        "core.infrastructure.text.input_adapter.pdf2png",
        return_value=[str(path) for path in page_paths],
    ) as render:
        result = normalize_document_images(pdf_path)

    assert result == page_paths
    render.assert_called_once_with(
        pdf_path.resolve(),
        tmp_path / "_normalized_images" / "contract_pdf",
        dpi=300,
    )


def test_directory_expands_png_jpg_and_pdf_in_source_order(tmp_path) -> None:
    jpg_path = tmp_path / "01.jpg"
    png_path = tmp_path / "02.png"
    pdf_path = tmp_path / "03.pdf"
    Image.new("RGB", (4, 4), "white").save(jpg_path, format="JPEG")
    Image.new("RGB", (4, 4), "white").save(png_path)
    pdf_path.write_bytes(b"pdf")
    pdf_page = tmp_path / "_normalized_images" / "03_pdf" / "page-01.png"

    with patch(
        "core.infrastructure.text.input_adapter.pdf2png",
        return_value=[str(pdf_page)],
    ):
        result = normalize_document_images(tmp_path)

    assert result[0].parent.name == "01_jpg"
    assert result[1] == png_path.resolve()
    assert result[2] == pdf_page
