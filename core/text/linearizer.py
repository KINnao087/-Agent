from __future__ import annotations

import re
from typing import Any

_PAGE_RE = re.compile(r"^(第\s*\d+\s*页|共\s*\d+\s*页|page\s*\d+)$", re.I)
_NOISE_RE = re.compile(r"^[\W_]+$")


def _normalize_text(text: object) -> str:
    """规范化单行文本，便于后续去噪和拼接。"""
    return " ".join(str(text or "").split()).strip()


def _box_sort_key(box: Any) -> tuple[float, float]:
    """从 OCR 框中提取近似的左上角坐标，用于排序。"""
    if isinstance(box, (list, tuple)) and box:
        first = box[0]
        if isinstance(first, (list, tuple)):
            xs = [float(point[0]) for point in box if isinstance(point, (list, tuple)) and len(point) >= 2]
            ys = [float(point[1]) for point in box if isinstance(point, (list, tuple)) and len(point) >= 2]
            if xs and ys:
                return min(ys), min(xs)
        if len(box) >= 2:
            return float(box[1]), float(box[0])
    return 0.0, 0.0


def _should_skip_line(text: str, score: float) -> bool:
    """过滤明显无效的 OCR 行。"""
    if not text:
        return True
    if score < 0.4:
        return True
    if _NOISE_RE.fullmatch(text):
        return True
    if _PAGE_RE.fullmatch(text):
        return True
    if text.isdigit() and len(text) <= 3:
        return True
    return False


def _merge_row_texts(texts: list[str]) -> str:
    """把同一行中的多个 OCR 片段合并成一行文本。"""
    return " ".join(text for text in texts if text).strip()


def linearize_ocr_page(page_ocr: dict) -> str:
    """把单页 OCR JSON 转成按阅读顺序展开的线性文本。"""
    texts = page_ocr.get("rec_texts") or []
    scores = page_ocr.get("rec_scores") or []
    boxes = page_ocr.get("rec_boxes") or []

    items: list[tuple[float, float, int, str]] = []
    for index, raw_text in enumerate(texts):
        text = _normalize_text(raw_text)
        score = float(scores[index]) if index < len(scores) and scores[index] is not None else 1.0
        if _should_skip_line(text, score):
            continue
        top, left = _box_sort_key(boxes[index] if index < len(boxes) else None)
        items.append((top, left, index, text))

    items.sort()

    # 先按纵向位置把文本框归并为“行”，再在行内按左到右排序。
    row_gap = 12.0
    rows: list[dict[str, Any]] = []
    for top, left, _, text in items:
        if not rows or abs(top - rows[-1]["top"]) > row_gap:
            rows.append({"top": top, "items": [(left, text)]})
            continue
        rows[-1]["items"].append((left, text))

    lines: list[str] = []
    for row in rows:
        row_items = sorted(row["items"], key=lambda item: item[0])
        line = _merge_row_texts([text for _, text in row_items])
        if not line:
            continue
        if lines and lines[-1] == line:
            continue
        lines.append(line)
    return "\n".join(lines)


def _linearize_page_list(page_list: list[dict]) -> list[str]:
    """把多页 OCR JSON 列表转成逐页线性文本列表。"""
    texts = [linearize_ocr_page(page) for page in page_list]
    return [text for text in texts if text]


def build_linearized_document(ocr_payload: dict) -> dict:
    """根据合同、附件、发票 OCR 结果生成线性化文档。"""
    contract_texts = _linearize_page_list(ocr_payload.get("contract", []))
    attachment_texts = _linearize_page_list(ocr_payload.get("attachments", []))
    invoice_texts = _linearize_page_list(ocr_payload.get("invoice", []))

    sections: list[str] = []
    if contract_texts:
        sections.append("【合同正文】\n" + "\n\n".join(contract_texts))
    if attachment_texts:
        sections.append(
            "\n\n".join(
                f"【附件{i}】\n{text}" for i, text in enumerate(attachment_texts, start=1)
            )
        )
    if invoice_texts:
        sections.append(
            "\n\n".join(
                f"【发票{i}】\n{text}" for i, text in enumerate(invoice_texts, start=1)
            )
        )

    return {
        "contract_texts": contract_texts,
        "attachment_texts": attachment_texts,
        "invoice_texts": invoice_texts,
        "full_text": "\n\n".join(sections).strip(),
    }
