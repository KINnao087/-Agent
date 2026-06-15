from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.infrastructure.vision.seal.detector import (
    MAX_BBOX_ASPECT_RATIO,
    MIN_BBOX_AREA,
    MIN_BBOX_HEIGHT,
    MIN_BBOX_WIDTH,
    build_candidate_bbox,
    find_red_contours,
    merge_candidate_bboxes,
)
from core.infrastructure.vision.seal.preprocessing import (
    build_red_mask,
    clean_red_mask,
)

DEFAULT_IMAGE_DIR = Path("test/seals/train_images")
RANDOM_SEED = 20260611


@dataclass(slots=True)
class CircleCandidate:
    bbox: list[int]
    score: float
    arc_coverage: float
    edge_support: float
    red_support: float


@dataclass(slots=True)
class AlgorithmStats:
    images: int
    detected: int
    missed: int
    detection_rate: float
    elapsed_seconds: float
    avg_ms_per_image: float
    candidate_avg: float
    candidate_min: int
    candidate_max: int
    missed_images: list[str]


def current_project_candidates(image: np.ndarray) -> list[list[int]]:
    clean_mask = clean_red_mask(build_red_mask(image))
    contours = find_red_contours(clean_mask)
    boxes = merge_candidate_bboxes(
        [build_candidate_bbox(contour) for contour in contours]
    )
    return [
        box
        for box in boxes
        if box[2] >= MIN_BBOX_WIDTH
        and box[3] >= MIN_BBOX_HEIGHT
        and box[2] * box[3] >= MIN_BBOX_AREA
        and max(box[2] / box[3], box[3] / box[2])
        <= MAX_BBOX_ASPECT_RATIO
    ][:10]


def _normalized_gray(image: np.ndarray) -> tuple[np.ndarray, float]:
    height, width = image.shape[:2]
    target_long_side = min(640, max(280, max(height, width)))
    resize_scale = target_long_side / max(height, width)
    resized = cv2.resize(
        image,
        None,
        fx=resize_scale,
        fy=resize_scale,
        interpolation=(
            cv2.INTER_CUBIC if resize_scale > 1 else cv2.INTER_AREA
        ),
    )
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    enhanced = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8)).apply(gray)
    return cv2.GaussianBlur(enhanced, (5, 5), 1.1), resize_scale


def _circle_features(
    edges: np.ndarray,
    red_mask: np.ndarray,
    center_x: float,
    center_y: float,
    radius: float,
) -> tuple[float, float, float]:
    angles = np.linspace(0, 2 * np.pi, 144, endpoint=False)
    edge_hits = []
    red_hits = []
    sector_hits = np.zeros(24, dtype=np.uint8)
    height, width = edges.shape

    for index, angle in enumerate(angles):
        cosine = np.cos(angle)
        sine = np.sin(angle)
        edge_hit = False
        red_hit = False
        for radial_offset in (-3, -1, 0, 1, 3):
            sample_radius = radius + radial_offset
            x = int(round(center_x + sample_radius * cosine))
            y = int(round(center_y + sample_radius * sine))
            if 0 <= x < width and 0 <= y < height:
                edge_hit = edge_hit or edges[y, x] > 0
                red_hit = red_hit or red_mask[y, x] > 0
        edge_hits.append(edge_hit)
        red_hits.append(red_hit)
        if edge_hit or red_hit:
            sector_hits[index * 24 // len(angles)] = 1

    return (
        float(np.mean(sector_hits)),
        float(np.mean(edge_hits)),
        float(np.mean(red_hits)),
    )


def _iou(box_a: list[int], box_b: list[int]) -> float:
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b
    intersection_width = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    intersection_height = max(0, min(ay + ah, by + bh) - max(ay, by))
    intersection = intersection_width * intersection_height
    union = aw * ah + bw * bh - intersection
    return intersection / union if union else 0.0


def _nms(
    candidates: list[CircleCandidate],
    iou_threshold: float = 0.35,
) -> list[CircleCandidate]:
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


def hough_candidates(image: np.ndarray) -> list[CircleCandidate]:
    gray, resize_scale = _normalized_gray(image)
    resized = cv2.resize(
        image,
        (gray.shape[1], gray.shape[0]),
        interpolation=cv2.INTER_AREA,
    )
    edges = cv2.Canny(gray, 45, 130)
    red_mask = build_red_mask(resized)
    minimum_side = min(gray.shape)
    all_candidates = []

    for pyramid_scale in (0.8, 1.0, 1.25):
        scaled_gray = cv2.resize(
            gray,
            None,
            fx=pyramid_scale,
            fy=pyramid_scale,
            interpolation=cv2.INTER_LINEAR,
        )
        scaled_minimum_side = min(scaled_gray.shape)
        circles = cv2.HoughCircles(
            scaled_gray,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=max(18, scaled_minimum_side // 5),
            param1=110,
            param2=17,
            minRadius=max(8, int(scaled_minimum_side * 0.14)),
            maxRadius=max(12, int(scaled_minimum_side * 0.58)),
        )
        if circles is None:
            continue

        for scaled_x, scaled_y, scaled_radius in circles[0][:40]:
            center_x = float(scaled_x / pyramid_scale)
            center_y = float(scaled_y / pyramid_scale)
            radius = float(scaled_radius / pyramid_scale)
            radius_ratio = radius / minimum_side
            if not 0.13 <= radius_ratio <= 0.60:
                continue

            arc_coverage, edge_support, red_support = _circle_features(
                edges,
                red_mask,
                center_x,
                center_y,
                radius,
            )
            if arc_coverage < 0.25:
                continue
            if edge_support < 0.08 and red_support < 0.06:
                continue

            original_x = center_x / resize_scale
            original_y = center_y / resize_scale
            original_radius = radius / resize_scale
            diameter = original_radius * 2
            area_ratio = (
                diameter * diameter / (image.shape[0] * image.shape[1])
            )
            center_distance = np.hypot(
                (original_x - image.shape[1] / 2) / image.shape[1],
                (original_y - image.shape[0] / 2) / image.shape[0],
            )
            if area_ratio < 0.12 or center_distance > 0.55:
                continue

            left = max(0, int(round(original_x - original_radius)))
            top = max(0, int(round(original_y - original_radius)))
            right = min(
                image.shape[1],
                int(round(original_x + original_radius)),
            )
            bottom = min(
                image.shape[0],
                int(round(original_y + original_radius)),
            )
            if right <= left or bottom <= top:
                continue

            score = (
                arc_coverage * 0.50
                + edge_support * 0.30
                + red_support * 0.20
            )
            if score < 0.42:
                continue
            all_candidates.append(
                CircleCandidate(
                    bbox=[left, top, right - left, bottom - top],
                    score=score,
                    arc_coverage=arc_coverage,
                    edge_support=edge_support,
                    red_support=red_support,
                )
            )

    return _nms(all_candidates)


def _evaluate(
    image_paths: list[Path],
    algorithm,
) -> AlgorithmStats:
    started = time.perf_counter()
    missed = []
    candidate_counts = []

    for image_path in image_paths:
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            missed.append(str(image_path))
            candidate_counts.append(0)
            continue
        candidates = algorithm(image)
        candidate_counts.append(len(candidates))
        if not candidates:
            missed.append(str(image_path))

    elapsed = time.perf_counter() - started
    detected = len(image_paths) - len(missed)
    return AlgorithmStats(
        images=len(image_paths),
        detected=detected,
        missed=len(missed),
        detection_rate=detected / len(image_paths),
        elapsed_seconds=elapsed,
        avg_ms_per_image=elapsed * 1000 / len(image_paths),
        candidate_avg=statistics.fmean(candidate_counts),
        candidate_min=min(candidate_counts),
        candidate_max=max(candidate_counts),
        missed_images=missed,
    )


def _sample_images(
    image_dir: Path,
    calibration_size: int,
    evaluation_size: int,
) -> tuple[list[Path], list[Path]]:
    images = sorted(
        image_dir.glob("*.jpg"),
        key=lambda path: int(path.stem),
    )
    if len(images) < calibration_size + evaluation_size:
        raise ValueError("Not enough images for the requested sample sizes")
    randomizer = random.Random(RANDOM_SEED)
    randomizer.shuffle(images)
    return (
        images[:calibration_size],
        images[calibration_size : calibration_size + evaluation_size],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-dir", type=Path, default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--calibration-size", type=int, default=200)
    parser.add_argument("--evaluation-size", type=int, default=1000)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/benchmarks/seal-hough-detection-report.json"
        ),
    )
    args = parser.parse_args()

    calibration, evaluation = _sample_images(
        args.image_dir,
        args.calibration_size,
        args.evaluation_size,
    )
    calibration_stats = _evaluate(calibration, hough_candidates)
    current_stats = _evaluate(evaluation, current_project_candidates)
    hough_stats = _evaluate(evaluation, hough_candidates)
    report = {
        "dataset": str(args.image_dir.resolve()),
        "dataset_images": len(list(args.image_dir.glob("*.jpg"))),
        "all_images_are_positive": True,
        "metric": "image-level detection rate (at least one candidate)",
        "random_seed": RANDOM_SEED,
        "calibration": {
            "images": args.calibration_size,
            "hough": asdict(calibration_stats),
        },
        "evaluation": {
            "images": args.evaluation_size,
            "sample_digest": hashlib.sha256(
                "\n".join(path.name for path in evaluation).encode()
            ).hexdigest(),
            "current": asdict(current_stats),
            "hough": asdict(hough_stats),
            "detection_rate_change_percentage_points": (
                hough_stats.detection_rate - current_stats.detection_rate
            )
            * 100,
        },
        "limitations": [
            "The dataset contains no negative images, so false-positive rate "
            "and precision cannot be measured.",
            "The current detector is evaluated with its exact candidate "
            "geometry filters but without writing crop artifacts.",
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
