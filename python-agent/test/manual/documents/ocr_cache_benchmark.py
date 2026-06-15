from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.infrastructure.text import normalize_document_images
from core.infrastructure.text.paddle_ocr import (
    clear_paddle_ocr_cache,
    create_paddle_ocr,
    get_paddle_ocr,
    predict_ocr_image,
)

DEFAULT_CONTRACT = Path("test/testfiles/contract/contract1.pdf")


@dataclass(slots=True)
class BenchmarkStats:
    name: str
    runs: int
    pages: int
    durations_seconds: list[float]
    avg_seconds: float
    min_seconds: float
    max_seconds: float
    text_digest: str
    text_chars: int
    results_consistent: bool


def _text_digest(results: list[dict]) -> tuple[str, int]:
    text = "\n".join(
        str(item)
        for result in results
        for item in result.get("rec_texts", [])
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest(), len(text)


def _run_contract(
    image_paths: list[Path],
    get_ocr: Callable[[], Any],
) -> tuple[list[dict], float]:
    started = time.perf_counter()
    results = [
        predict_ocr_image(get_ocr(), str(image_path))
        for image_path in image_paths
    ]
    return results, time.perf_counter() - started


def _benchmark(
    name: str,
    image_paths: list[Path],
    runs: int,
    get_ocr: Callable[[], Any],
) -> BenchmarkStats:
    durations = []
    digests = []
    text_chars = []

    for run_index in range(1, runs + 1):
        results, duration = _run_contract(image_paths, get_ocr)
        digest, char_count = _text_digest(results)
        durations.append(duration)
        digests.append(digest)
        text_chars.append(char_count)
        print(
            f"{name} run={run_index}/{runs} "
            f"seconds={duration:.3f} text_chars={char_count}",
            flush=True,
        )

    return BenchmarkStats(
        name=name,
        runs=runs,
        pages=len(image_paths),
        durations_seconds=durations,
        avg_seconds=statistics.fmean(durations),
        min_seconds=min(durations),
        max_seconds=max(durations),
        text_digest=digests[0],
        text_chars=text_chars[0],
        results_consistent=len(set(digests)) == 1,
    )


def run_strategy(
    strategy: str,
    contract_path: Path,
    runs: int,
    device: str,
) -> BenchmarkStats:
    image_paths = normalize_document_images(contract_path)
    if strategy == "old":
        return _benchmark(
            name="new_instance_per_page",
            image_paths=image_paths,
            runs=runs,
            get_ocr=lambda: create_paddle_ocr(device),
        )

    if strategy == "cached":
        clear_paddle_ocr_cache()
        return _benchmark(
            name="lazy_singleton_cached",
            image_paths=image_paths,
            runs=runs,
            get_ocr=lambda: get_paddle_ocr(device),
        )

    raise ValueError(f"Unknown strategy: {strategy}")


def _run_isolated_strategy(
    strategy: str,
    contract_path: Path,
    runs: int,
    device: str,
    log_dir: Path,
) -> BenchmarkStats:
    result_path = log_dir / f"{strategy}-result.json"
    log_path = log_dir / f"{strategy}.log"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--contract",
        str(contract_path),
        "--runs",
        str(runs),
        "--device",
        device,
        "--worker-strategy",
        strategy,
        "--worker-output",
        str(result_path),
    ]
    with log_path.open("w", encoding="utf-8") as log_file:
        subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=True,
        )
    return BenchmarkStats(**json.loads(result_path.read_text(encoding="utf-8")))


def run_benchmark(
    contract_path: Path,
    runs: int,
    device: str,
    log_dir: Path,
) -> dict:
    log_dir.mkdir(parents=True, exist_ok=True)
    old = _run_isolated_strategy(
        "old", contract_path, runs, device, log_dir
    )
    cached = _run_isolated_strategy(
        "cached", contract_path, runs, device, log_dir
    )
    speedup = old.avg_seconds / cached.avg_seconds
    return {
        "contract_path": str(contract_path.resolve()),
        "device": device,
        "runs_per_strategy": runs,
        "pages_per_run": old.pages,
        "timing_scope": (
            "OCR initialization and inference for all pages; "
            "PDF-to-PNG normalization excluded"
        ),
        "process_isolation": True,
        "old": asdict(old),
        "cached": asdict(cached),
        "comparison": {
            "average_speedup": speedup,
            "average_time_saved_seconds": old.avg_seconds - cached.avg_seconds,
            "average_time_saved_percent": (1 - cached.avg_seconds / old.avg_seconds) * 100,
            "ocr_text_consistent": old.text_digest == cached.text_digest,
            "old_runs_consistent": old.results_consistent,
            "cached_runs_consistent": cached.results_consistent,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--device", choices=("cpu", "gpu"), default="gpu")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/benchmarks/ocr-cache-report.json"),
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path("artifacts/benchmarks/ocr-cache-logs"),
    )
    parser.add_argument(
        "--worker-strategy",
        choices=("old", "cached"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker_strategy:
        stats = run_strategy(
            args.worker_strategy,
            args.contract,
            args.runs,
            args.device,
        )
        if args.worker_output is None:
            raise ValueError("--worker-output is required in worker mode")
        args.worker_output.parent.mkdir(parents=True, exist_ok=True)
        args.worker_output.write_text(
            json.dumps(asdict(stats), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return

    report = run_benchmark(
        args.contract,
        args.runs,
        args.device,
        args.log_dir,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report={args.output.resolve()}")


if __name__ == "__main__":
    main()
