from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from seal_all_datasets_hybrid_benchmark import rectangle_fallback_candidates
from seal_hough_detection_benchmark import (
    current_project_candidates,
    hough_candidates,
)

DEFAULT_SEALS_DIR = Path("test/seals")
DATASET_NAMES = ("train_images2", "train_images3", "train_images4")


@dataclass(slots=True)
class ClassificationStats:
    images: int
    positives: int
    negatives: int
    true_positives: int
    false_negatives: int
    true_negatives: int
    false_positives: int
    recall: float
    precision: float
    specificity: float
    false_positive_rate: float
    accuracy: float
    f1: float
    elapsed_seconds: float
    avg_ms_per_image: float
    false_negative_images: list[str]
    false_positive_images: list[str]


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _label_from_path(path: Path) -> int:
    label = path.stem.rsplit("_", 1)[-1]
    if label not in {"0", "1"}:
        raise ValueError(f"Missing _0/_1 label suffix: {path}")
    return int(label)


def _build_stats(
    samples: list[tuple[Path, int]],
    predictions: list[bool],
    elapsed_seconds: float,
) -> ClassificationStats:
    true_positives = false_negatives = true_negatives = false_positives = 0
    false_negative_images = []
    false_positive_images = []

    for (path, label), predicted in zip(samples, predictions, strict=True):
        if label == 1 and predicted:
            true_positives += 1
        elif label == 1:
            false_negatives += 1
            false_negative_images.append(str(path))
        elif predicted:
            false_positives += 1
            false_positive_images.append(str(path))
        else:
            true_negatives += 1

    positives = true_positives + false_negatives
    negatives = true_negatives + false_positives
    recall = _ratio(true_positives, positives)
    precision = _ratio(true_positives, true_positives + false_positives)
    return ClassificationStats(
        images=len(samples),
        positives=positives,
        negatives=negatives,
        true_positives=true_positives,
        false_negatives=false_negatives,
        true_negatives=true_negatives,
        false_positives=false_positives,
        recall=recall,
        precision=precision,
        specificity=_ratio(true_negatives, negatives),
        false_positive_rate=_ratio(false_positives, negatives),
        accuracy=_ratio(true_positives + true_negatives, len(samples)),
        f1=_ratio(2 * precision * recall, precision + recall),
        elapsed_seconds=elapsed_seconds,
        avg_ms_per_image=elapsed_seconds * 1000 / len(samples),
        false_negative_images=false_negative_images,
        false_positive_images=false_positive_images,
    )


def _evaluate_simple(
    samples: list[tuple[Path, int]],
    algorithm: Callable[[np.ndarray], list],
) -> ClassificationStats:
    predictions = []
    started = time.perf_counter()
    for path, _ in samples:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Failed to read image: {path}")
        predictions.append(bool(algorithm(image)))
    return _build_stats(samples, predictions, time.perf_counter() - started)


def _evaluate_hough_and_hybrid(
    samples: list[tuple[Path, int]],
) -> tuple[ClassificationStats, ClassificationStats, dict]:
    hough_predictions = []
    hybrid_predictions = []
    hough_elapsed = 0.0
    fallback_elapsed = 0.0
    fallback_invocations = 0
    fallback_positive_predictions = 0

    for path, _ in samples:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Failed to read image: {path}")

        started = time.perf_counter()
        hough_detected = bool(hough_candidates(image))
        hough_elapsed += time.perf_counter() - started
        hough_predictions.append(hough_detected)
        if hough_detected:
            hybrid_predictions.append(True)
            continue

        fallback_invocations += 1
        started = time.perf_counter()
        rectangle_detected = bool(rectangle_fallback_candidates(image))
        fallback_elapsed += time.perf_counter() - started
        fallback_positive_predictions += int(rectangle_detected)
        hybrid_predictions.append(rectangle_detected)

    return (
        _build_stats(samples, hough_predictions, hough_elapsed),
        _build_stats(
            samples,
            hybrid_predictions,
            hough_elapsed + fallback_elapsed,
        ),
        {
            "invocations": fallback_invocations,
            "positive_predictions": fallback_positive_predictions,
            "elapsed_seconds": fallback_elapsed,
        },
    )


def _samples(test_dir: Path) -> list[tuple[Path, int]]:
    paths = sorted(test_dir.glob("*.png"))
    return [(path, _label_from_path(path)) for path in paths]


def _aggregate(items: list[ClassificationStats]) -> dict:
    true_positives = sum(item.true_positives for item in items)
    false_negatives = sum(item.false_negatives for item in items)
    true_negatives = sum(item.true_negatives for item in items)
    false_positives = sum(item.false_positives for item in items)
    positives = true_positives + false_negatives
    negatives = true_negatives + false_positives
    images = positives + negatives
    recall = _ratio(true_positives, positives)
    precision = _ratio(true_positives, true_positives + false_positives)
    elapsed = sum(item.elapsed_seconds for item in items)
    return {
        "images": images,
        "positives": positives,
        "negatives": negatives,
        "true_positives": true_positives,
        "false_negatives": false_negatives,
        "true_negatives": true_negatives,
        "false_positives": false_positives,
        "recall": recall,
        "precision": precision,
        "specificity": _ratio(true_negatives, negatives),
        "false_positive_rate": _ratio(false_positives, negatives),
        "accuracy": _ratio(true_positives + true_negatives, images),
        "f1": _ratio(2 * precision * recall, precision + recall),
        "elapsed_seconds": elapsed,
        "avg_ms_per_image": elapsed * 1000 / images,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seals-dir", type=Path, default=DEFAULT_SEALS_DIR)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/benchmarks/seal-mixed-classification-report.json"
        ),
    )
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    reports = {}
    all_current = []
    all_hough = []
    all_hybrid = []
    fallback_totals = {
        "invocations": 0,
        "positive_predictions": 0,
        "elapsed_seconds": 0.0,
    }

    for dataset_name in DATASET_NAMES:
        samples = _samples(args.seals_dir / dataset_name / "test")
        if args.limit:
            samples = samples[: args.limit]
        current = _evaluate_simple(samples, current_project_candidates)
        hough, hybrid, fallback = _evaluate_hough_and_hybrid(samples)
        reports[dataset_name] = {
            "current": asdict(current),
            "hough": asdict(hough),
            "hybrid": asdict(hybrid),
            "rectangle_fallback": fallback,
        }
        all_current.append(current)
        all_hough.append(hough)
        all_hybrid.append(hybrid)
        for key in fallback_totals:
            fallback_totals[key] += fallback[key]
        print(
            f"{dataset_name}: current={current.accuracy:.4f} "
            f"hough={hough.accuracy:.4f} hybrid={hybrid.accuracy:.4f}",
            flush=True,
        )

    report = {
        "seals_dir": str(args.seals_dir.resolve()),
        "label_rule": "filename suffix _0=negative, _1=positive",
        "datasets": reports,
        "overall": {
            "current": _aggregate(all_current),
            "hough": _aggregate(all_hough),
            "hybrid": _aggregate(all_hybrid),
            "rectangle_fallback": fallback_totals,
        },
        "limitations": [
            "Negative samples are generated background images derived from "
            "the same source pairs as positive pages.",
            "This benchmark scores page-level presence only, not candidate "
            "localization IoU.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report["overall"], ensure_ascii=False, indent=2))
    print(f"report={args.output.resolve()}")


if __name__ == "__main__":
    main()
