from __future__ import annotations

from pathlib import Path

from core.infrastructure.vision.seal import check_contract_seals


def check_contract_seals_service(input_path: str) -> dict[str, str]:
    """接收合同图片文件夹路径，并转调底层签章审核实现。"""
    contract_dir = Path(input_path)
    return check_contract_seals(contract_dir)
