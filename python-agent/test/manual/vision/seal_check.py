from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.infrastructure.vision.seal import check_contract_seals

DEFAULT_INPUT_DIR = (
    ROOT_DIR
    / "test"
    / "testfiles"
    / "contract"
    / "_pdf_pages"
    / "contract1"
)


def main() -> None:
    """直接运行 infrastructure 层的签章审核链路，并打印结构化结果。"""
    input_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_INPUT_DIR
    if not input_dir.exists():
        raise FileNotFoundError(f"input dir not found: {input_dir}")
    if not input_dir.is_dir():
        raise NotADirectoryError(f"input dir is not a directory: {input_dir}")

    result = check_contract_seals(input_dir)

    print(f"输入目录: {input_dir}")
    print("check_contract_seals 返回结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
