from __future__ import annotations

import json
import threading
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
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def _lock_for(self, review_id: str) -> threading.Lock:
        """获取按 review_id 粒度的锁，保证同名审核互不阻塞。"""
        with self._locks_guard:
            if review_id not in self._locks:
                self._locks[review_id] = threading.Lock()
            return self._locks[review_id]

    def review_dir(self, review_id: str) -> Path:
        return self.root / review_id

    def manifest_path(self, review_id: str) -> Path:
        return self.review_dir(review_id) / "manifest.json"

    def load(self, review_id: str) -> ReviewManifest:
        return ReviewManifest.model_validate_json(
            self.manifest_path(review_id).read_text(encoding="utf-8")
        )

    def find_by_material(self, material_fingerprint: str) -> ReviewManifest | None:
        # 只读操作，原子写入保证不会读到半成品
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
        with self._lock_for(review_id):
            # 双重检查：锁内再次确认没有竞态创建
            double_check = self.find_by_material(material_fingerprint)
            if double_check:
                return double_check
            self._save_locked(manifest)
        return manifest

    def save(self, manifest: ReviewManifest) -> None:
        with self._lock_for(manifest.review_id):
            self._save_locked(manifest)

    def _save_locked(self, manifest: ReviewManifest) -> None:
        """不加锁的内部写入，调用方需持有 review_id 锁。"""
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
        with self._lock_for(review_id):
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
