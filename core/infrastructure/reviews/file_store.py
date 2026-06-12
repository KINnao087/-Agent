from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.domain.reviews import ReviewManifest
from core.shared.path_utils import ensure_directory


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FileReviewStore:
    def __init__(self, root: str | Path = "artifacts/reviews") -> None:
        self.root = ensure_directory(root)

    def review_dir(self, review_id: str) -> Path:
        return self.root / review_id

    def manifest_path(self, review_id: str) -> Path:
        return self.review_dir(review_id) / "manifest.json"

    def load(self, review_id: str) -> ReviewManifest:
        return ReviewManifest.model_validate_json(
            self.manifest_path(review_id).read_text(encoding="utf-8")
        )

    def find_by_material(self, material_fingerprint: str) -> ReviewManifest | None:
        for path in sorted(self.root.glob("review_*/manifest.json")):
            manifest = ReviewManifest.model_validate_json(path.read_text(encoding="utf-8"))
            if manifest.material_fingerprint == material_fingerprint:
                return manifest
        return None

    def create_or_load(
        self,
        *,
        contract_fingerprint: str,
        material_fingerprint: str,
        inputs: dict[str, Any],
    ) -> ReviewManifest:
        existing = self.find_by_material(material_fingerprint)
        if existing:
            return existing

        review_id = f"review_{material_fingerprint[:16]}"
        now = _now()
        manifest = ReviewManifest(
            review_id=review_id,
            contract_fingerprint=contract_fingerprint,
            material_fingerprint=material_fingerprint,
            inputs=inputs,
            created_at=now,
            updated_at=now,
        )
        self.save(manifest)
        return manifest

    def save(self, manifest: ReviewManifest) -> None:
        target_dir = ensure_directory(self.review_dir(manifest.review_id))
        for name in ("inputs", "normalized", "ocr", "results", "reports"):
            ensure_directory(target_dir / name)
        manifest.updated_at = _now()
        target = self.manifest_path(manifest.review_id)
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(manifest.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)

    def write_result(
        self,
        review_id: str,
        relative_path: str,
        payload: Any,
    ) -> Path:
        target = self.review_dir(review_id) / relative_path
        ensure_directory(target.parent)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return target

    def read_result(self, review_id: str, relative_path: str) -> Any:
        path = self.review_dir(review_id) / relative_path
        return json.loads(path.read_text(encoding="utf-8"))
