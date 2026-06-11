from pathlib import Path

from core.application.workflows.cross_page_seal import CROSS_PAGE_SEAL_GRAPH
from core.domain.contracts import CPSealResult


def check_cpseal_services(input_path: str | Path) -> CPSealResult:
    return CROSS_PAGE_SEAL_GRAPH.invoke(
        {"input_path": str(input_path)}
    )["result"]
