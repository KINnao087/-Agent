from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from core.contracts.continuity_service import check_contract_continuity
from core.text import parse_folder_to_json_list

TEST_CONTRACT_DIR = Path("test/testfiles/contract")


def main() -> None:
    """直接跑完整链路：合同图片 -> OCR -> AI -> 连续性结果。"""
    print(f"读取合同目录: {TEST_CONTRACT_DIR}")
    contract_pages = parse_folder_to_json_list(TEST_CONTRACT_DIR)

    if not contract_pages:
        raise ValueError(f"未读取到合同页 OCR 结果: {TEST_CONTRACT_DIR}")

    print(f"OCR 页数: {len(contract_pages)}")
    result = check_contract_continuity(contract_pages)

    print("连续性检测结果:")
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
