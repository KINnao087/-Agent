from __future__ import annotations

import argparse
import json
import statistics
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

from seal_hough_detection_benchmark import (
    current_project_candidates,
    hough_candidates,
)

DEFAULT_SEALS_DIR = Path("test/seals")


@dataclass(slots=True)
class RectangleCandidate:
    bbox: list[int]
    score: float
    fill_ratio: float
    solidity: float
    edge_density: float
    texture_std: float


@dataclass(slots=True)
class AlgorithmStats:
    images: int
    detected: int
    missed: int
    detection_rate: float
    elapsed_seconds: float
    avg_ms_per_image: float
    candidate_average: float
    candidate_max: int
    missed_images: list[str]


@dataclass(slots=True)
class DatasetReport:
    dataset: str
    images: int
    current: AlgorithmStats
    hough: AlgorithmStats
    hybrid: AlgorithmStats
    rectangle_fallback_invocations: int
    rectangle_fallback_recovered: int
    rectangle_fallback_recovery_rate: float | None


def _iou(box_a: list[int], box_b: list[int]) -> float:
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b
    intersection_width = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    intersection_height = max(0, min(ay + ah, by + bh) - max(ay, by))
    intersection = intersection_width * intersection_height
    union = aw * ah + bw * bh - intersection
    return intersection / union if union else 0.0


def _rectangle_nms(
    candidates: list[RectangleCandidate],
    iou_threshold: float = 0.35,
) -> list[RectangleCandidate]:
    kept = []
    for candidate in sorted(
        candidates,
        key=lambda value: value.score,
        reverse=True,
    ):
        if all(
            _iou(candidate.bbox, existing.bbox) < iou_threshold
            for existing in kept
        ):
            kept.append(candidate)
    return kept[:3]


def rectangle_fallback_candidates(
    image: np.ndarray,
) -> list[RectangleCandidate]:
    height, width = image.shape[:2]
    target_long_side = min(1200, max(420, max(height, width)))
    scale = target_long_side / max(height, width)
    resized = cv2.resize(
        image,
        None,
        fx=scale,
        fy=scale,
        interpolation=cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA,
    )
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    enhanced = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8),
    ).apply(gray)
    binary = cv2.adaptiveThreshold(
        enhanced,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        35,
        9,
    )
    edges = cv2.Canny(enhanced, 45, 135)
    binary = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)),
        iterations=1,
    )
    combined = cv2.bitwise_or(binary, edges)
    closed = cv2.morphologyEx(
        combined,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
        iterations=1,
    )
    contours, _ = cv2.findContours(
        closed,
        cv2.RETR_LIST,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    resized_area = resized.shape[0] * resized.shape[1]
    candidates = []
    for contour in contours:
        contour_area = cv2.contourArea(contour)
        if contour_area <= 0:
            continue

        rotated_rect = cv2.minAreaRect(contour)
        rect_width, rect_height = rotated_rect[1]
        if rect_width < 18 or rect_height < 18:
            continue

        rectangle_area = rect_width * rect_height
        area_ratio = rectangle_area / resized_area
        aspect_ratio = max(
            rect_width / rect_height,
            rect_height / rect_width,
        )
        if not 0.0006 <= area_ratio <= 0.30:
            continue
        if aspect_ratio > 4.5:
            continue

        fill_ratio = contour_area / rectangle_area
        hull_area = cv2.contourArea(cv2.convexHull(contour))
        solidity = contour_area / hull_area if hull_area else 0.0
        if fill_ratio < 0.18 or solidity < 0.50:
            continue

        x, y, box_width, box_height = cv2.boundingRect(contour)
        region_edges = edges[y : y + box_height, x : x + box_width]
        region_gray = gray[y : y + box_height, x : x + box_width]
        edge_density = float(np.count_nonzero(region_edges)) / region_edges.size
        texture_std = float(np.std(region_gray))
        if not 0.020 <= edge_density <= 0.38:
            continue
        if texture_std < 9.0:
            continue

        perimeter = cv2.arcLength(contour, True)
        vertices = len(
            cv2.approxPolyDP(contour, 0.025 * perimeter, True)
        )
        if not 3 <= vertices <= 12:
            continue

        box_points = cv2.boxPoints(rotated_rect)
        left = max(0, int(np.floor(np.min(box_points[:, 0]) / scale)))
        top = max(0, int(np.floor(np.min(box_points[:, 1]) / scale)))
        right = min(width, int(np.ceil(np.max(box_points[:, 0]) / scale)))
        bottom = min(height, int(np.ceil(np.max(box_points[:, 1]) / scale)))
        if right <= left or bottom <= top:
            continue

        shape_score = max(0.0, 1.0 - abs(aspect_ratio - 1.5) / 3.0)
        score = (
            fill_ratio * 0.30
            + solidity * 0.25
            + min(edge_density / 0.20, 1.0) * 0.25
            + min(texture_std / 50.0, 1.0) * 0.10
            + shape_score * 0.10
        )
        if score < 0.38:
            continue

        candidates.append(
            RectangleCandidate(
                bbox=[left, top, right - left, bottom - top],
                score=score,
                fill_ratio=fill_ratio,
                solidity=solidity,
                edge_density=edge_density,
                texture_std=texture_std,
            )
        )

    return _rectangle_nms(candidates)


def _dataset_paths(seals_dir: Path) -> dict[str, list[Path]]:
    return {
        "train_images": sorted(
            (seals_dir / "train_images").glob("*.jpg"),
            key=lambda path: int(path.stem),
        ),
        "train_images2": sorted(
            (seals_dir / "train_images2" / "gen_imgs").glob("*.png")
        ),
        "train_images3": sorted(
            (seals_dir / "train_images3" / "gen_imgs").glob("*.png")
        ),
    }


def _build_stats(
    image_paths: list[Path],
    detections: list[bool],
    candidate_counts: list[int],
    elapsed_seconds: float,
) -> AlgorithmStats:
    missed_images = [
        str(path)
        for path, detected in zip(image_paths, detections, strict=True)
        if not detected
    ]
    detected = len(image_paths) - len(missed_images)
    return AlgorithmStats(
        images=len(image_paths),
        detected=detected,
        missed=len(missed_images),
        detection_rate=detected / len(image_paths),
        elapsed_seconds=elapsed_seconds,
        avg_ms_per_image=elapsed_seconds * 1000 / len(image_paths),
        candidate_average=statistics.fmean(candidate_counts),
        candidate_max=max(candidate_counts),
        missed_images=missed_images,
    )


def _evaluate_simple(
    image_paths: list[Path],
    algorithm: Callable[[np.ndarray], list],
) -> AlgorithmStats:
    detections = []
    candidate_counts = []
    started = time.perf_counter()
    for image_path in image_paths:
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Failed to read image: {image_path}")
        candidates = algorithm(image)
        detections.append(bool(candidates))
        candidate_counts.append(len(candidates))
    elapsed = time.perf_counter() - started
    return _build_stats(
        image_paths,
        detections,
        candidate_counts,
        elapsed,
    )


def _evaluate_hough_and_hybrid(
    image_paths: list[Path],
) -> tuple[AlgorithmStats, AlgorithmStats, int, int]:
    hough_detections = []
    hough_candidate_counts = []
    hybrid_detections = []
    hybrid_candidate_counts = []
    hough_elapsed = 0.0
    fallback_elapsed = 0.0
    fallback_invocations = 0
    fallback_recovered = 0

    for image_path in image_paths:
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Failed to read image: {image_path}")

        started = time.perf_counter()
        circles = hough_candidates(image)
        hough_elapsed += time.perf_counter() - started
        hough_detected = bool(circles)
        hough_detections.append(hough_detected)
        hough_candidate_counts.append(len(circles))

        if hough_detected:
            hybrid_detections.append(True)
            hybrid_candidate_counts.append(len(circles))
            continue

        fallback_invocations += 1
        started = time.perf_counter()
        rectangles = rectangle_fallback_candidates(image)
        fallback_elapsed += time.perf_counter() - started
        rectangle_detected = bool(rectangles)
        fallback_recovered += int(rectangle_detected)
        hybrid_detections.append(rectangle_detected)
        hybrid_candidate_counts.append(len(rectangles))

    hough_stats = _build_stats(
        image_paths,
        hough_detections,
        hough_candidate_counts,
        hough_elapsed,
    )
    hybrid_stats = _build_stats(
        image_paths,
        hybrid_detections,
        hybrid_candidate_counts,
        hough_elapsed + fallback_elapsed,
    )
    return (
        hough_stats,
        hybrid_stats,
        fallback_invocations,
        fallback_recovered,
    )


def _evaluate_dataset(
    dataset_name: str,
    image_paths: list[Path],
) -> DatasetReport:
    current = _evaluate_simple(image_paths, current_project_candidates)
    hough, hybrid, invocations, recovered = _evaluate_hough_and_hybrid(
        image_paths
    )
    return DatasetReport(
        dataset=dataset_name,
        images=len(image_paths),
        current=current,
        hough=hough,
        hybrid=hybrid,
        rectangle_fallback_invocations=invocations,
        rectangle_fallback_recovered=recovered,
        rectangle_fallback_recovery_rate=(
            recovered / invocations if invocations else None
        ),
    )


def _aggregate(
    reports: list[DatasetReport],
    algorithm_name: str,
) -> dict:
    stats = [getattr(report, algorithm_name) for report in reports]
    images = sum(item.images for item in stats)
    detected = sum(item.detected for item in stats)
    elapsed = sum(item.elapsed_seconds for item in stats)
    return {
        "images": images,
        "detected": detected,
        "missed": images - detected,
        "detection_rate": detected / images,
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
            "artifacts/benchmarks/seal-all-datasets-hybrid-report.json"
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit each dataset for a smoke test",
    )
    args = parser.parse_args()

    datasets = _dataset_paths(args.seals_dir)
    if args.limit:
        datasets = {
            name: paths[: args.limit]
            for name, paths in datasets.items()
        }

    reports = []
    for dataset_name, image_paths in datasets.items():
        print(
            f"dataset={dataset_name} images={len(image_paths)}",
            flush=True,
        )
        report = _evaluate_dataset(dataset_name, image_paths)
        reports.append(report)
        print(
            f"current={report.current.detection_rate:.4f} "
            f"hough={report.hough.detection_rate:.4f} "
            f"hybrid={report.hybrid.detection_rate:.4f} "
            f"recovered={report.rectangle_fallback_recovered}",
            flush=True,
        )

    output = {
        "seals_dir": str(args.seals_dir.resolve()),
        "all_images_treated_as_positive": True,
        "mask_pixels_read": False,
        "dataset_count": len(reports),
        "total_images": sum(report.images for report in reports),
        "datasets": {
            report.dataset: asdict(report)
            for report in reports
        },
        "overall": {
            "current": _aggregate(reports, "current"),
            "hough": _aggregate(reports, "hough"),
            "hybrid": _aggregate(reports, "hybrid"),
            "rectangle_fallback_invocations": sum(
                report.rectangle_fallback_invocations
                for report in reports
            ),
            "rectangle_fallback_recovered": sum(
                report.rectangle_fallback_recovered
                for report in reports
            ),
        },
        "limitations": [
            "All 5270 images are treated as positive under the supplied "
            "filename rule, so false-positive rate cannot be measured.",
            "Mask pixels are not read; candidate localization is not scored.",
            "Hybrid timing equals Hough time plus rectangle fallback time "
            "only for Hough misses, matching the requested serial flow.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(output["overall"], ensure_ascii=False, indent=2))
    print(f"report={args.output.resolve()}")


if __name__ == "__main__":
    main()
