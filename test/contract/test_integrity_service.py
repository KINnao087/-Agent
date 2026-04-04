from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.contracts.integrity_service import check_contract_integrity, check_contract_all
from core.text import parse_folder_to_json_list
from core.vision.seal.detector import detect_seal_candidates

# TEST_CONTRACT_DIR = Path("test/testfiles/contract")
TEST_CONTRACT_DIR = Path("test/testfiles/contract1_simulated_tampering")

def collect_seal_candidates(contract_pages: list[dict[str, object]]) -> list:
    """对合同末尾几页做签章候选检测。"""
    candidates = []
    total_pages = len(contract_pages)
    start_index = max(0, total_pages - 3)

    for page_index, page in enumerate(contract_pages[start_index:], start=start_index + 1):
        image_path = page.get("input_path")
        if not isinstance(image_path, str) or not image_path:
            continue

        page_candidates = detect_seal_candidates(image_path=image_path, page_index=page_index)
        candidates.extend(page_candidates)

    return candidates


def main() -> None:
    """直接跑完整链路：合同图片 -> OCR -> AI -> 完整性校验结果。"""
    # print(f"读取合同目录: {TEST_CONTRACT_DIR}")
    # contract_pages = parse_folder_to_json_list(TEST_CONTRACT_DIR)
    #
    # if not contract_pages:
    #     raise ValueError(f"未读取到合同页 OCR 结果: {TEST_CONTRACT_DIR}")
    #
    # print(f"OCR 页数: {len(contract_pages)}")
    # print("检测签章候选图...")
    # seal_candidates = collect_seal_candidates(contract_pages)
    # print(f"签章候选数量: {len(seal_candidates)}")
    result = check_contract_all(TEST_CONTRACT_DIR)

    print("check_contract_integrity 返回结果:")
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
