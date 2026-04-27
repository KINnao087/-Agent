from pathlib import Path
from typing import List, Dict
from core.infrastructure.vision.seal import check_contract_seals

def check_contract_seals_service(contract_paths: List[str]) -> Dict[str, str]:
    return_dict = {}

    paths = []
    for path in contract_paths:
        paths.append(Path(path))

    check_contract_seals(paths)


    return return_dict