from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.infrastructure.text.paddle_ocr import (
    clear_paddle_ocr_cache,
    get_paddle_ocr,
    predict_ocr_image,
)

DEFAULT_IMAGE_DIR = Path(
    "test/testfiles/contracts/seal1/_pdf_pages/seal1"
)


@dataclass(slots=True)
class RunStats:
    seconds: float
    cache_hits: int
    cache_misses: int
    hash_seconds: float


@dataclass(slots=True)
class StrategyStats:
    strategy: str
    group: str
    runs: int
    requests_per_run: int
    unique_images: int
    durations_seconds: list[float]
    avg_seconds: float
    min_seconds: float
    max_seconds: float
    cache_hits_per_run: list[int]
    cache_misses_per_run: list[int]
    hash_seconds_per_run: list[float]
    total_cache_hits: int
    total_cache_misses: int
    result_digest: str
    results_consistent: bool


def _sha256_file(path: Path) -> tuple[str, float]:
    started = time.perf_counter()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest, time.perf_counter() - started


def _result_digest(results: list[dict[str, Any]]) -> str:
    canonical = [
        {
            "rec_texts": result.get("rec_texts", []),
            "rec_boxes": result.get("rec_boxes", []),
            "rec_scores": result.get("rec_scores", []),
        }
        for result in results
    ]
    payload = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_image_groups(image_dir: Path) -> dict[str, list[Path]]:
    images = sorted(image_dir.glob("*.png"))[:10]
    if len(images) < 10:
        raise ValueError(f"At least 10 PNG images are required: {image_dir}")

    hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in images]
    if len(set(hashes)) != 10:
        raise ValueError("The unique-image group contains duplicate file content")

    duplicate_group = [
        images[0],
        images[1],
        images[0],
        images[2],
        images[1],
        images[3],
        images[4],
        images[2],
        images[3],
        images[4],
    ]
    return {
        "unique_10_of_10": images,
        "duplicate_5_of_10": duplicate_group,
    }


def _run_current(image_paths: list[Path], device: str) -> tuple[list[dict], RunStats]:
    started = time.perf_counter()
    ocr = get_paddle_ocr(device)
    results = [
        predict_ocr_image(ocr, str(image_path))
        for image_path in image_paths
    ]
    return results, RunStats(
        seconds=time.perf_counter() - started,
        cache_hits=0,
        cache_misses=0,
        hash_seconds=0.0,
    )


def _run_disk_cache(
    image_paths: list[Path],
    device: str,
    cache_dir: Path,
) -> tuple[list[dict], RunStats]:
    started = time.perf_counter()
    hits = 0
    misses = 0
    hash_seconds = 0.0
    results = []

    for image_path in image_paths:
        key, elapsed = _sha256_file(image_path)
        hash_seconds += elapsed
        cache_path = cache_dir / f"{key}.json"

        if cache_path.is_file():
            result = json.loads(cache_path.read_text(encoding="utf-8"))
            result["input_path"] = str(image_path)
            hits += 1
        else:
            result = predict_ocr_image(get_paddle_ocr(device), str(image_path))
            cache_path.write_text(
                json.dumps(result, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            misses += 1
        results.append(result)

    return results, RunStats(
        seconds=time.perf_counter() - started,
        cache_hits=hits,
        cache_misses=misses,
        hash_seconds=hash_seconds,
    )


def run_strategy(
    strategy: str,
    group_name: str,
    image_paths: list[Path],
    runs: int,
    device: str,
    cache_dir: Path,
) -> StrategyStats:
    clear_paddle_ocr_cache()
    if strategy == "disk_cache":
        shutil.rmtree(cache_dir, ignore_errors=True)
        cache_dir.mkdir(parents=True)

    run_stats = []
    digests = []
    for run_index in range(1, runs + 1):
        if strategy == "current":
            results, stats = _run_current(image_paths, device)
        else:
            results, stats = _run_disk_cache(image_paths, device, cache_dir)

        run_stats.append(stats)
        digests.append(_result_digest(results))
        print(
            f"strategy={strategy} group={group_name} "
            f"run={run_index}/{runs} seconds={stats.seconds:.3f} "
            f"hits={stats.cache_hits} misses={stats.cache_misses}",
            flush=True,
        )

    durations = [stats.seconds for stats in run_stats]
    return StrategyStats(
        strategy=strategy,
        group=group_name,
        runs=runs,
        requests_per_run=len(image_paths),
        unique_images=len(
            {
                hashlib.sha256(path.read_bytes()).hexdigest()
                for path in image_paths
            }
        ),
        durations_seconds=durations,
        avg_seconds=statistics.fmean(durations),
        min_seconds=min(durations),
        max_seconds=max(durations),
        cache_hits_per_run=[stats.cache_hits for stats in run_stats],
        cache_misses_per_run=[stats.cache_misses for stats in run_stats],
        hash_seconds_per_run=[stats.hash_seconds for stats in run_stats],
        total_cache_hits=sum(stats.cache_hits for stats in run_stats),
        total_cache_misses=sum(stats.cache_misses for stats in run_stats),
        result_digest=digests[0],
        results_consistent=len(set(digests)) == 1,
    )


def _run_isolated(
    strategy: str,
    group: str,
    args: argparse.Namespace,
) -> StrategyStats:
    worker_result = args.work_dir / f"{group}-{strategy}.json"
    log_path = args.work_dir / f"{group}-{strategy}.log"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--image-dir",
        str(args.image_dir),
        "--runs",
        str(args.runs),
        "--device",
        args.device,
        "--work-dir",
        str(args.work_dir),
        "--worker-strategy",
        strategy,
        "--worker-group",
        group,
        "--worker-output",
        str(worker_result),
    ]
    with log_path.open("w", encoding="utf-8") as log_file:
        subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=True,
        )
    return StrategyStats(
        **json.loads(worker_result.read_text(encoding="utf-8"))
    )


def _comparison(current: StrategyStats, cached: StrategyStats) -> dict[str, Any]:
    return {
        "speedup": current.avg_seconds / cached.avg_seconds,
        "avg_seconds_saved": current.avg_seconds - cached.avg_seconds,
        "avg_percent_saved": (
            1 - cached.avg_seconds / current.avg_seconds
        ) * 100,
        "ocr_results_equal": current.result_digest == cached.result_digest,
        "current_results_consistent": current.results_consistent,
        "cached_results_consistent": cached.results_consistent,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-dir", type=Path, default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--device", choices=("cpu", "gpu"), default="gpu")
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path("artifacts/benchmarks/ocr-disk-result-cache"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/benchmarks/ocr-disk-result-cache-report.json"
        ),
    )
    parser.add_argument(
        "--worker-strategy",
        choices=("current", "disk_cache"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--worker-group", help=argparse.SUPPRESS)
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    groups = _load_image_groups(args.image_dir)
    args.work_dir.mkdir(parents=True, exist_ok=True)

    if args.worker_strategy:
        image_paths = groups[args.worker_group]
        stats = run_strategy(
            args.worker_strategy,
            args.worker_group,
            image_paths,
            args.runs,
            args.device,
            args.work_dir / f"{args.worker_group}-cache",
        )
        args.worker_output.write_text(
            json.dumps(asdict(stats), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return

    report: dict[str, Any] = {
        "image_dir": str(args.image_dir.resolve()),
        "device": args.device,
        "runs_per_strategy_per_group": args.runs,
        "process_isolation": True,
        "cache_lifecycle": (
            "empty at the start of each group, persistent across its 10 runs"
        ),
        "timing_scope": (
            "image read, SHA-256, disk lookup/read/write, OCR initialization "
            "and inference as applicable"
        ),
        "groups": {},
    }
    for group_name in groups:
        current = _run_isolated("current", group_name, args)
        cached = _run_isolated("disk_cache", group_name, args)
        report["groups"][group_name] = {
            "current": asdict(current),
            "disk_cache": asdict(cached),
            "comparison": _comparison(current, cached),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report={args.output.resolve()}")


if __name__ == "__main__":
    main()
