from __future__ import annotations

from core.domain.reviews import ReviewStepRecord


def is_step_current(
    record: ReviewStepRecord | None,
    required_versions: dict[str, str],
) -> bool:
    return bool(
        record
        and record.status == "completed"
        and record.versions == required_versions
    )
