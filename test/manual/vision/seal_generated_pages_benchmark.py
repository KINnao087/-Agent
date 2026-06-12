from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from seal_hough_detection_benchmark import (
    current_project_candidates,
    hough_candidates,
)

DEFAULT_IMAGE_DIR = Path("test/seals/train_images2/gen_imgs")
DEFAULT_MASK_DIR = Path("test/seals/train_images2/gen_masks")


@dataclass(slots=True)
class ClassificationStats:
    images: int
    positives: int
    negatives: int
    true_positives: int
    false_negatives: int
    true_negatives: int
    false_positives: int
    recall: float | None
    precision: float | None
    specificity: float | None
    false_positive_rate: float | None
    accuracy: float
    elapsed_seconds: float
    avg_ms_per_image: float
    candidate_average: float
    candidate_max: int
    false_negative_images: list[str]
    false_positive_images: list[str]


def _load_labels(
    image_dir: Path,
    mask_dir: Path,
) -> tuple[list[tuple[Path, bool]], dict[str, int]]:
    mask_stems = {path.stem for path in mask_dir.glob("*.*")}
    samples = []
    positive_and_negative_masks = 0
    missing_masks = 0

    for image_path in sorted(image_dir.glob("*.*")):
        positive_mask = f"{image_path.stem}_1" in mask_stems
        negative_mask = f"{image_path.stem}_0" in mask_stems
        if positive_mask and negative_mask:
            positive_and_negative_masks += 1
        if not positive_mask and not negative_mask:
            missing_masks += 1
            continue
        samples.append((image_path, positive_mask))

    return samples, {
        "dual_mask_images": positive_and_negative_masks,
        "missing_mask_images": missing_masks,
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _evaluate(samples, algorithm) -> ClassificationStats:
    started = time.perf_counter()
    true_positives = false_negatives = true_negatives = false_positives = 0
    false_negative_images = []
    false_positive_images = []
    candidate_counts = []

    for image_path, expected_positive in samples:
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Failed to read image: {image_path}")
        candidates = algorithm(image)
        predicted_positive = bool(candidates)
        candidate_counts.append(len(candidates))

        if expected_positive and predicted_positive:
            true_positives += 1
        elif expected_positive:
            false_negatives += 1
            false_negative_images.append(str(image_path))
        elif predicted_positive:
            false_positives += 1
            false_positive_images.append(str(image_path))
        else:
            true_negatives += 1

    elapsed = time.perf_counter() - started
    positives = true_positives + false_negatives
    negatives = true_negatives + false_positives
    return ClassificationStats(
        images=len(samples),
        positives=positives,
        negatives=negatives,
        true_positives=true_positives,
        false_negatives=false_negatives,
        true_negatives=true_negatives,
        false_positives=false_positives,
        recall=_ratio(true_positives, positives),
        precision=_ratio(true_positives, true_positives + false_positives),
        specificity=_ratio(true_negatives, negatives),
        false_positive_rate=_ratio(false_positives, negatives),
        accuracy=(true_positives + true_negatives) / len(samples),
        elapsed_seconds=elapsed,
        avg_ms_per_image=elapsed * 1000 / len(samples),
        candidate_average=sum(candidate_counts) / len(candidate_counts),
        candidate_max=max(candidate_counts),
        false_negative_images=false_negative_images,
        false_positive_images=false_positive_images,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-dir", type=Path, default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--mask-dir", type=Path, default=DEFAULT_MASK_DIR)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/benchmarks/seal-generated-pages-report.json"
        ),
    )
    args = parser.parse_args()

    samples, label_diagnostics = _load_labels(
        args.image_dir,
        args.mask_dir,
    )
    current = _evaluate(samples, current_project_candidates)
    hough = _evaluate(samples, hough_candidates)
    report = {
        "image_dir": str(args.image_dir.resolve()),
        "mask_dir": str(args.mask_dir.resolve()),
        "mask_pixels_read": False,
        "label_rule": (
            "<image_stem>_1.* exists => positive; otherwise "
            "<image_stem>_0.* exists => negative"
        ),
        "label_diagnostics": label_diagnostics,
        "current": asdict(current),
        "hough": asdict(hough),
        "recall_change_percentage_points": (
            (hough.recall or 0) - (current.recall or 0)
        )
        * 100,
        "limitations": [
            "Every image has both a _0 and a _1 mask file, so the filename "
            "rule labels all images positive.",
            "No negative samples are available under this interpretation; "
            "specificity and false-positive rate cannot be calculated.",
            "Mask pixels were not read, so candidate localization cannot be "
            "validated against the seal region.",
        ],
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
