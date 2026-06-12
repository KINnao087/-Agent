from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ReviewStepStatus = Literal[
    "pending",
    "running",
    "completed",
    "failed",
    "skipped",
    "stale",
]


class ReviewStepRecord(BaseModel):
    status: ReviewStepStatus = "pending"
    result_path: str = ""
    versions: dict[str, str] = Field(default_factory=dict)
    error: str = ""
    updated_at: str = ""


class ReviewManifest(BaseModel):
    review_id: str
    contract_fingerprint: str
    material_fingerprint: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    normalized_pages: dict[str, list[str]] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)
    steps: dict[str, ReviewStepRecord] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
