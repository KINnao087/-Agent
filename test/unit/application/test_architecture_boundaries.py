from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_only_chat_workflow_uses_langgraph() -> None:
    offenders = []
    for path in (PROJECT_ROOT / "core" / "application").rglob("*.py"):
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        if (
            relative == "core/application/workflows/chat.py"
            or relative.startswith("core/application/agent/")
        ):
            continue
        text = path.read_text(encoding="utf-8")
        if "langgraph" in text or "StateGraph" in text:
            offenders.append(relative)

    assert offenders == []


def test_application_services_do_not_import_fixed_business_workflows() -> None:
    offenders = []
    roots = [
        PROJECT_ROOT / "core" / "application" / "contracts",
        PROJECT_ROOT / "core" / "application" / "documents",
        PROJECT_ROOT / "core" / "application" / "reviews",
    ]
    for root in roots:
        for path in root.rglob("*.py"):
            if "core.application.workflows" in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(PROJECT_ROOT).as_posix())

    assert offenders == []
