from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import optuna

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_SEALS_DIR = Path("test/seals")
DEFAULT_WORK_DIR = Path("artifacts/benchmarks/hough-tpe")
RANDOM_SEED = 20260612


@dataclass(slots=True)
class ScalePriors:
    min_radius_ratio: float
    max_radius_ratio: float
    min_area_ratio: float
    max_area_ratio: float
    edge_roi_width_ratio: float
    source_components: int


@dataclass(slots=True)
class CandidateFeatures:
    arc_coverage: float
    edge_support: float
    red_support: float
    ring_contrast: float
    center_distance: float


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _metrics(labels: list[int], predictions: list[bool]) -> dict[str, float | int]:
    tp = sum(label == 1 and prediction for label, prediction in zip(labels, predictions))
    fn = sum(label == 1 and not prediction for label, prediction in zip(labels, predictions))
    tn = sum(label == 0 and not prediction for label, prediction in zip(labels, predictions))
    fp = sum(label == 0 and prediction for label, prediction in zip(labels, predictions))
    recall = _ratio(tp, tp + fn)
    precision = _ratio(tp, tp + fp)
    specificity = _ratio(tn, tn + fp)
    return {
        "true_positives": tp,
        "false_negatives": fn,
        "true_negatives": tn,
        "false_positives": fp,
        "recall": recall,
        "precision": precision,
        "specificity": specificity,
        "false_positive_rate": _ratio(fp, tn + fp),
        "accuracy": _ratio(tp + tn, len(labels)),
        "f1": _ratio(2 * precision * recall, precision + recall),
    }


def _foreground_components(mask_path: Path) -> list[tuple[int, int, int, int, np.ndarray]]:
    image = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    foreground = np.uint8(image < 250) * 255
    grouped = cv2.morphologyEx(
        foreground,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21)),
        iterations=2,
    )
    grouped = cv2.dilate(
        grouped,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)),
        iterations=1,
    )
    contours, _ = cv2.findContours(
        grouped,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    return [
        (*cv2.boundingRect(contour), foreground)
        for contour in contours
        if cv2.boundingRect(contour)[2] * cv2.boundingRect(contour)[3] >= 1500
    ]


def derive_scale_priors(mask_dir: Path) -> ScalePriors:
    radius_ratios = []
    area_ratios = []
    edge_width_ratios = []

    for mask_path in sorted(mask_dir.glob("*_1.png")):
        image = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        image_area = image.shape[0] * image.shape[1]
        short_side = min(image.shape)
        for x, y, width, height, foreground in _foreground_components(mask_path):
            radius = max(width, height) / 2
            radius_ratios.append(radius / short_side)
            area_ratios.append(width * height / image_area)

            region = foreground[y : y + height, x : x + width]
            distance = cv2.distanceTransform(region, cv2.DIST_L2, 5)
            positive_distances = distance[distance > 0]
            if positive_distances.size:
                stroke_half_width = float(np.percentile(positive_distances, 90))
                edge_width_ratios.append(stroke_half_width / radius)

    return ScalePriors(
        min_radius_ratio=float(np.percentile(radius_ratios, 0.5) * 0.80),
        max_radius_ratio=float(np.percentile(radius_ratios, 99.5) * 1.10),
        min_area_ratio=float(np.percentile(area_ratios, 0.5) * 0.75),
        max_area_ratio=float(np.percentile(area_ratios, 99.5) * 1.20),
        edge_roi_width_ratio=float(np.percentile(edge_width_ratios, 95)),
        source_components=len(radius_ratios),
    )


def _red_mask(image: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    return cv2.bitwise_or(
        cv2.inRange(hsv, np.array([0, 45, 10]), np.array([14, 255, 255])),
        cv2.inRange(hsv, np.array([166, 45, 10]), np.array([180, 255, 255])),
    )


def _sample_ring(
    edges: np.ndarray,
    red_mask: np.ndarray,
    center_x: float,
    center_y: float,
    radius: float,
    edge_width: int,
) -> CandidateFeatures:
    angles = np.linspace(0, 2 * np.pi, 144, endpoint=False)
    sector_hits = np.zeros(24, dtype=np.uint8)
    edge_hits = []
    red_hits = []
    inner_hits = []
    outer_hits = []
    height, width = edges.shape
    offsets = np.linspace(-edge_width, edge_width, 5)

    for index, angle in enumerate(angles):
        cosine = math.cos(angle)
        sine = math.sin(angle)
        edge_hit = red_hit = False
        for offset in offsets:
            sample_radius = radius + offset
            x = int(round(center_x + sample_radius * cosine))
            y = int(round(center_y + sample_radius * sine))
            if 0 <= x < width and 0 <= y < height:
                edge_hit = edge_hit or edges[y, x] > 0
                red_hit = red_hit or red_mask[y, x] > 0

        def edge_at(sample_radius: float) -> bool:
            x = int(round(center_x + sample_radius * cosine))
            y = int(round(center_y + sample_radius * sine))
            return 0 <= x < width and 0 <= y < height and edges[y, x] > 0

        edge_hits.append(edge_hit)
        red_hits.append(red_hit)
        inner_hits.append(edge_at(radius * 0.70))
        outer_hits.append(edge_at(radius * 1.20))
        if edge_hit or red_hit:
            sector_hits[index * len(sector_hits) // len(angles)] = 1

    edge_support = float(np.mean(edge_hits))
    surrounding_support = (float(np.mean(inner_hits)) + float(np.mean(outer_hits))) / 2
    return CandidateFeatures(
        arc_coverage=float(np.mean(sector_hits)),
        edge_support=edge_support,
        red_support=float(np.mean(red_hits)),
        ring_contrast=float(np.clip(edge_support - surrounding_support + 0.5, 0, 1)),
        center_distance=0.0,
    )


def generate_candidates(image: np.ndarray, priors: ScalePriors) -> list[CandidateFeatures]:
    height, width = image.shape[:2]
    target_long_side = min(800, max(360, max(height, width)))
    resize_scale = target_long_side / max(height, width)
    resized = cv2.resize(
        image,
        None,
        fx=resize_scale,
        fy=resize_scale,
        interpolation=cv2.INTER_CUBIC if resize_scale > 1 else cv2.INTER_AREA,
    )
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    gray = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8)).apply(gray)
    gray = cv2.GaussianBlur(gray, (5, 5), 1.1)
    edges = cv2.Canny(gray, 45, 130)
    red_mask = _red_mask(resized)
    resized_short_side = min(gray.shape)
    candidates = []

    for pyramid_scale in (0.8, 1.0, 1.25):
        scaled_gray = cv2.resize(
            gray,
            None,
            fx=pyramid_scale,
            fy=pyramid_scale,
            interpolation=cv2.INTER_LINEAR,
        )
        scaled_short_side = min(scaled_gray.shape)
        circles = cv2.HoughCircles(
            scaled_gray,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=max(12, int(scaled_short_side * priors.min_radius_ratio)),
            param1=110,
            param2=10,
            minRadius=max(
                4,
                int(scaled_short_side * priors.min_radius_ratio),
            ),
            maxRadius=max(
                8,
                int(scaled_short_side * priors.max_radius_ratio),
            ),
        )
        if circles is None:
            continue

        for scaled_x, scaled_y, scaled_radius in circles[0][:100]:
            center_x = float(scaled_x / pyramid_scale)
            center_y = float(scaled_y / pyramid_scale)
            radius = float(scaled_radius / pyramid_scale)
            radius_ratio = radius / resized_short_side
            area_ratio = (
                (radius * 2 / resize_scale) ** 2 / (height * width)
            )
            if not priors.min_radius_ratio <= radius_ratio <= priors.max_radius_ratio:
                continue
            if not priors.min_area_ratio <= area_ratio <= priors.max_area_ratio:
                continue

            edge_width = int(
                np.clip(radius * priors.edge_roi_width_ratio, 2, 12)
            )
            features = _sample_ring(
                edges,
                red_mask,
                center_x,
                center_y,
                radius,
                edge_width,
            )
            features.center_distance = float(
                np.hypot(
                    (center_x - resized.shape[1] / 2) / resized.shape[1],
                    (center_y - resized.shape[0] / 2) / resized.shape[0],
                )
            )
            candidates.append(features)

    unique = []
    seen = set()
    for candidate in candidates:
        signature = (
            round(candidate.arc_coverage, 2),
            round(candidate.edge_support, 2),
            round(candidate.red_support, 2),
            round(candidate.ring_contrast, 2),
            round(candidate.center_distance, 2),
        )
        if signature not in seen:
            seen.add(signature)
            unique.append(candidate)
    return unique


def _load_samples(test_dir: Path) -> list[tuple[Path, int]]:
    samples = []
    for path in sorted(test_dir.glob("*.png")):
        label = int(path.stem.rsplit("_", 1)[-1])
        samples.append((path, label))
    return samples


def build_feature_cache(
    dataset_name: str,
    test_dir: Path,
    priors: ScalePriors,
    cache_dir: Path,
) -> dict[str, Any]:
    cache_path = cache_dir / f"{dataset_name}.json"
    if cache_path.is_file():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    pages = []
    started = time.perf_counter()
    for index, (path, label) in enumerate(_load_samples(test_dir), start=1):
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Failed to read image: {path}")
        candidates = generate_candidates(image, priors)
        pages.append(
            {
                "path": str(path),
                "label": label,
                "candidates": [asdict(candidate) for candidate in candidates],
            }
        )
        if index % 25 == 0:
            print(
                f"features dataset={dataset_name} page={index}/{len(_load_samples(test_dir))}",
                flush=True,
            )

    payload = {
        "dataset": dataset_name,
        "elapsed_seconds": time.perf_counter() - started,
        "pages": pages,
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    return payload


def _predict_page(candidates: list[dict], params: dict[str, float]) -> bool:
    raw_weights = np.array(
        [
            params["arc_weight"],
            params["edge_weight"],
            params["red_weight"],
            params["contrast_weight"],
        ]
    )
    weights = raw_weights / raw_weights.sum()
    for candidate in candidates:
        if candidate["arc_coverage"] < params["min_arc_coverage"]:
            continue
        if candidate["edge_support"] < params["min_edge_support"]:
            continue
        if candidate["ring_contrast"] < params["min_ring_contrast"]:
            continue
        if candidate["center_distance"] > params["max_center_distance"]:
            continue
        score = float(
            np.dot(
                weights,
                [
                    candidate["arc_coverage"],
                    candidate["edge_support"],
                    candidate["red_support"],
                    candidate["ring_contrast"],
                ],
            )
        )
        if score >= params["score_threshold"]:
            return True
    return False


def evaluate(pages: list[dict], params: dict[str, float]) -> dict[str, float | int]:
    labels = [page["label"] for page in pages]
    predictions = [
        _predict_page(page["candidates"], params)
        for page in pages
    ]
    return _metrics(labels, predictions)


def _trial_params(trial: optuna.Trial) -> dict[str, float]:
    return {
        "min_arc_coverage": trial.suggest_float("min_arc_coverage", 0.25, 0.95),
        "min_edge_support": trial.suggest_float("min_edge_support", 0.05, 0.75),
        "min_ring_contrast": trial.suggest_float("min_ring_contrast", 0.35, 0.90),
        "max_center_distance": trial.suggest_float("max_center_distance", 0.35, 0.85),
        "arc_weight": trial.suggest_float("arc_weight", 0.05, 1.0),
        "edge_weight": trial.suggest_float("edge_weight", 0.05, 1.0),
        "red_weight": trial.suggest_float("red_weight", 0.0, 0.50),
        "contrast_weight": trial.suggest_float("contrast_weight", 0.05, 1.0),
        "score_threshold": trial.suggest_float("score_threshold", 0.25, 0.90),
    }


def optimize(
    train_pages: list[dict],
    validation_pages: list[dict],
    trials: int,
) -> optuna.Study:
    def objective(trial: optuna.Trial) -> float:
        params = _trial_params(trial)
        train = evaluate(train_pages, params)
        validation = evaluate(validation_pages, params)
        min_recall = min(train["recall"], validation["recall"])
        mean_fpr = (train["false_positive_rate"] + validation["false_positive_rate"]) / 2
        mean_f1 = (train["f1"] + validation["f1"]) / 2
        trial.set_user_attr("train", train)
        trial.set_user_attr("validation", validation)
        if min_recall < 0.95:
            return min_recall - 2.0 - mean_fpr
        return 2.0 + (1 - mean_fpr) * 0.75 + mean_f1 * 0.25

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(
            seed=RANDOM_SEED,
            multivariate=True,
        ),
    )
    study.optimize(objective, n_trials=trials, show_progress_bar=True)
    return study


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seals-dir", type=Path, default=DEFAULT_SEALS_DIR)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--trials", type=int, default=300)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/benchmarks/hough-tpe-report.json"),
    )
    args = parser.parse_args()

    priors = derive_scale_priors(
        args.seals_dir / "train_images2" / "gen_masks"
    )
    args.work_dir.mkdir(parents=True, exist_ok=True)
    (args.work_dir / "scale-priors.json").write_text(
        json.dumps(asdict(priors), indent=2),
        encoding="utf-8",
    )

    caches = {}
    for dataset_name in ("train_images2", "train_images3", "train_images4"):
        caches[dataset_name] = build_feature_cache(
            dataset_name,
            args.seals_dir / dataset_name / "test",
            priors,
            args.work_dir,
        )

    study = optimize(
        caches["train_images2"]["pages"],
        caches["train_images3"]["pages"],
        args.trials,
    )
    best_params = study.best_params
    train_metrics = evaluate(caches["train_images2"]["pages"], best_params)
    validation_metrics = evaluate(
        caches["train_images3"]["pages"],
        best_params,
    )
    test_started = time.perf_counter()
    test_metrics = evaluate(caches["train_images4"]["pages"], best_params)
    test_filter_seconds = time.perf_counter() - test_started

    report = {
        "method": "Optuna TPE over cached lenient Hough candidates",
        "random_seed": RANDOM_SEED,
        "trials": args.trials,
        "split": {
            "optimization": "train_images2/test",
            "validation": "train_images3/test",
            "final_test": "train_images4/test",
        },
        "scale_priors": asdict(priors),
        "fixed_generation_parameters": {
            "target_long_side": 800,
            "pyramid_scales": [0.8, 1.0, 1.25],
            "hough_dp": 1.2,
            "hough_param1": 110,
            "hough_param2": 10,
            "clahe_clip_limit": 2.2,
            "gaussian_kernel": [5, 5],
            "gaussian_sigma": 1.1,
            "canny": [45, 130],
        },
        "optimized_parameters": best_params,
        "best_objective": study.best_value,
        "metrics": {
            "optimization": train_metrics,
            "validation": validation_metrics,
            "final_test": test_metrics,
        },
        "feature_generation_seconds": {
            name: cache["elapsed_seconds"]
            for name, cache in caches.items()
        },
        "final_test_filter_seconds": test_filter_seconds,
        "top_trials": [
            {
                "number": trial.number,
                "value": trial.value,
                "params": trial.params,
                "train": trial.user_attrs.get("train"),
                "validation": trial.user_attrs.get("validation"),
            }
            for trial in sorted(
                study.trials,
                key=lambda trial: trial.value or float("-inf"),
                reverse=True,
            )[:10]
        ],
        "limitations": [
            "Hough generation parameters are fixed; TPE optimizes candidate "
            "filtering and scoring parameters.",
            "Negative pages are generated background counterparts paired "
            "with positive pages.",
            "The final test set is evaluated once after optimization.",
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
