import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.infrastructure.text import parse_file_to_json

FILE_PATH = PROJECT_ROOT / "test" / "fixtures" / "ocr" / "test.png"
ocr_json = parse_file_to_json(FILE_PATH)
print(ocr_json)
