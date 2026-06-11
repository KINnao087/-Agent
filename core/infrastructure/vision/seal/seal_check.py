from __future__ import annotations

import json
from pathlib import Path

from core.infrastructure.ai import invoke_structured
from core.infrastructure.ai.prompts import SEAL_REVIEW_PROMPT
from core.infrastructure.ai.schemas import SealPageReviewResponse

from .detector import detect_seal_candidates

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def _image_paths(input_path: str | Path) -> list[Path]:
    path = Path(input_path)
    if not path.is_dir():
        raise NotADirectoryError(path)
    return sorted(
        item
        for item in path.iterdir()
        if item.is_file() and item.suffix.lower() in IMAGE_SUFFIXES
    )


def check_contract_seals(input_path: str | Path) -> dict[str, str]:
    page_results = []
    seal_page_paths = []

    for page_index, image_path in enumerate(_image_paths(input_path), start=1):
        candidates = detect_seal_candidates(image_path=image_path, page_index=page_index)
        if candidates:
            seal_page_paths.append(str(image_path))
            review = invoke_structured(
                SEAL_REVIEW_PROMPT,
                SealPageReviewResponse,
                {
                    "page_index": page_index,
                    "candidates": "\n".join(
                        f"{index}: {candidate.bbox}"
                        for index, candidate in enumerate(candidates)
                    ),
                    "pages_text": "",
                },
                image_paths=[image_path],
            ).model_dump()
        else:
            review = {"candidate_reviews": []}

        page_results.append(
            {
                "page_index": page_index,
                "image_path": str(image_path),
                "candidate_count": len(candidates),
                "review": review,
            }
        )

    payload = {
        "input_path": str(Path(input_path)),
        "seal_page_paths": seal_page_paths,
        "page_results": page_results,
    }
    return {"ok": True, "output": json.dumps(payload, ensure_ascii=False, indent=2)}
