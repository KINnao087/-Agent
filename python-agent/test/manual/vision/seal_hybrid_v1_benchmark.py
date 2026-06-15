from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.infrastructure.vision.seal.hybrid_detector import (
    HybridSealModel,
    extract_page_features,
)

RANDOM_SEED = 20260612
DATASET_NAMES = ("train_images2", "train_images3", "train_images4")
DEFAULT_MODEL_PATH = Path(
    "models/seal_hybrid_v1.json"
)


@dataclass(slots=True)
class Metrics:
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
    false_negative_images: list[str]
    false_positive_images: list[str]


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _metrics(
    paths: list[str],
    labels: np.ndarray,
    predictions: np.ndarray,
) -> Metrics:
    true_positives = int(np.sum(predictions & (labels == 1)))
    false_negatives = int(np.sum(~predictions & (labels == 1)))
    true_negatives = int(np.sum(~predictions & (labels == 0)))
    false_positives = int(np.sum(predictions & (labels == 0)))
    positives = true_positives + false_negatives
    negatives = true_negatives + false_positives
    recall = _ratio(true_positives, positives)
    precision = _ratio(true_positives, true_positives + false_positives)
    return Metrics(
        images=len(labels),
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
        accuracy=_ratio(true_positives + true_negatives, len(labels)),
        f1=_ratio(2 * precision * recall, precision + recall),
        false_negative_images=[
            path
            for path, label, prediction in zip(
                paths,
                labels,
                predictions,
                strict=True,
            )
            if label == 1 and not prediction
        ],
        false_positive_images=[
            path
            for path, label, prediction in zip(
                paths,
                labels,
                predictions,
                strict=True,
            )
            if label == 0 and prediction
        ],
    )


def _load_dataset(
    dataset_dir: Path,
    cache_path: Path,
) -> dict[str, object]:
    paths = sorted(dataset_dir.glob("*.png"))
    if cache_path.is_file():
        cached = np.load(cache_path, allow_pickle=False)
        cached_paths = cached["paths"].tolist()
        if cached_paths == [str(path) for path in paths]:
            return {
                "paths": cached_paths,
                "labels": cached["labels"],
                "features": cached["features"],
                "candidate_counts": cached["candidate_counts"],
                "max_candidate_scores": cached["max_candidate_scores"],
                "feature_seconds": float(cached["feature_seconds"][0]),
                "from_cache": True,
            }

    labels = []
    features = []
    candidate_counts = []
    max_candidate_scores = []
    started = time.perf_counter()
    for index, path in enumerate(paths, start=1):
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Failed to load image: {path}")
        page_features, candidates = extract_page_features(image)
        labels.append(int(path.stem.rsplit("_", 1)[-1]))
        features.append(page_features)
        candidate_counts.append(len(candidates))
        max_candidate_scores.append(
            max((candidate.score for candidate in candidates), default=0.0)
        )
        if index % 30 == 0:
            print(f"{dataset_dir.parent.name}: {index}/{len(paths)}", flush=True)

    feature_seconds = time.perf_counter() - started
    payload = {
        "paths": [str(path) for path in paths],
        "labels": np.asarray(labels, dtype=np.int8),
        "features": np.asarray(features, dtype=np.float64),
        "candidate_counts": np.asarray(candidate_counts, dtype=np.int16),
        "max_candidate_scores": np.asarray(
            max_candidate_scores,
            dtype=np.float64,
        ),
        "feature_seconds": feature_seconds,
        "from_cache": False,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        cache_path,
        paths=np.asarray(payload["paths"]),
        labels=payload["labels"],
        features=payload["features"],
        candidate_counts=payload["candidate_counts"],
        max_candidate_scores=payload["max_candidate_scores"],
        feature_seconds=np.asarray([feature_seconds]),
    )
    return payload


def _fit_model(
    train_features: np.ndarray,
    train_labels: np.ndarray,
) -> tuple[StandardScaler, LogisticRegression]:
    scaler = StandardScaler()
    normalized = scaler.fit_transform(train_features)
    classifier = LogisticRegression(
        C=0.1,
        class_weight="balanced",
        max_iter=3000,
        random_state=RANDOM_SEED,
    )
    classifier.fit(normalized, train_labels)
    return scaler, classifier


def _scores(
    scaler: StandardScaler,
    classifier: LogisticRegression,
    features: np.ndarray,
) -> np.ndarray:
    return classifier.predict_proba(scaler.transform(features))[:, 1]


def _select_threshold(
    labels: np.ndarray,
    scores: np.ndarray,
    minimum_recall: float = 0.95,
) -> dict[str, float]:
    choices = []
    for threshold in np.unique(scores):
        metrics = _metrics(
            [""] * len(labels),
            labels,
            scores >= threshold,
        )
        if metrics.recall < minimum_recall:
            continue
        choices.append(
            (
                metrics.false_positive_rate,
                -metrics.precision,
                -threshold,
                threshold,
                metrics,
            )
        )
    if not choices:
        raise ValueError("No validation threshold satisfies the recall constraint")
    _, _, _, threshold, metrics = min(choices)
    return {
        "threshold": float(threshold),
        "recall": metrics.recall,
        "precision": metrics.precision,
        "false_positive_rate": metrics.false_positive_rate,
    }


def _evaluate_variant(
    feature_count: int,
    datasets: dict[str, dict[str, object]],
) -> tuple[dict[str, object], HybridSealModel]:
    train = datasets["train_images2"]
    validation = datasets["train_images3"]
    scaler, classifier = _fit_model(
        train["features"][:, :feature_count],
        train["labels"],
    )
    validation_scores = _scores(
        scaler,
        classifier,
        validation["features"][:, :feature_count],
    )
    threshold = _select_threshold(
        validation["labels"],
        validation_scores,
    )

    results = {}
    for name, dataset in datasets.items():
        scores = _scores(
            scaler,
            classifier,
            dataset["features"][:, :feature_count],
        )
        results[name] = {
            "metrics": asdict(
                _metrics(
                    dataset["paths"],
                    dataset["labels"],
                    scores >= threshold["threshold"],
                )
            ),
            "score_summary": {
                "positive_min": float(np.min(scores[dataset["labels"] == 1])),
                "positive_mean": float(np.mean(scores[dataset["labels"] == 1])),
                "negative_mean": float(np.mean(scores[dataset["labels"] == 0])),
                "negative_max": float(np.max(scores[dataset["labels"] == 0])),
            },
        }

    scale = np.asarray(scaler.scale_, dtype=np.float64)
    scale[scale == 0] = 1.0
    model = HybridSealModel(
        mean=np.asarray(scaler.mean_, dtype=np.float64),
        scale=scale,
        weights=np.asarray(classifier.coef_[0], dtype=np.float64),
        intercept=float(classifier.intercept_[0]),
        threshold=threshold["threshold"],
    )
    return {
        "feature_count": feature_count,
        "threshold_selection": threshold,
        "datasets": results,
    }, model


def _candidate_summary(dataset: dict[str, object]) -> dict[str, float | int]:
    labels = dataset["labels"]
    counts = dataset["candidate_counts"]
    return {
        "positive_pages_with_candidates": int(
            np.sum((labels == 1) & (counts > 0))
        ),
        "negative_pages_with_candidates": int(
            np.sum((labels == 0) & (counts > 0))
        ),
        "positive_average_candidates": float(np.mean(counts[labels == 1])),
        "negative_average_candidates": float(np.mean(counts[labels == 0])),
    }


def _aggregate(results: dict[str, object]) -> dict[str, float | int]:
    metrics = [result["metrics"] for result in results.values()]
    true_positives = sum(item["true_positives"] for item in metrics)
    false_negatives = sum(item["false_negatives"] for item in metrics)
    true_negatives = sum(item["true_negatives"] for item in metrics)
    false_positives = sum(item["false_positives"] for item in metrics)
    positives = true_positives + false_negatives
    negatives = true_negatives + false_positives
    images = positives + negatives
    recall = _ratio(true_positives, positives)
    precision = _ratio(true_positives, true_positives + false_positives)
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
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seals-dir", type=Path, default=Path("test/seals"))
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("artifacts/benchmarks/seal-hybrid-v1"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/benchmarks/seal-hybrid-v1-report.json"),
    )
    parser.add_argument(
        "--model-output",
        type=Path,
        default=DEFAULT_MODEL_PATH,
    )
    parser.add_argument(
        "--hough-report",
        type=Path,
        default=Path(
            "artifacts/benchmarks/seal-mixed-classification-report.json"
        ),
    )
    args = parser.parse_args()

    datasets = {
        name: _load_dataset(
            args.seals_dir / name / "test",
            args.cache_dir / f"{name}.npz",
        )
        for name in DATASET_NAMES
    }
    page_feature_count = 32 * 45 * 2 + 4
    page_only, _ = _evaluate_variant(page_feature_count, datasets)
    hybrid, model = _evaluate_variant(
        datasets["train_images2"]["features"].shape[1],
        datasets,
    )
    page_only["overall"] = _aggregate(page_only["datasets"])
    hybrid["overall"] = _aggregate(hybrid["datasets"])

    model_payload = model.to_dict()
    model_payload["metadata"] = {
        "algorithm": "hybrid_v1",
        "train_split": "train_images2/test",
        "validation_split": "train_images3/test",
        "random_seed": RANDOM_SEED,
        "feature_count": hybrid["feature_count"],
    }
    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    args.model_output.write_text(
        json.dumps(model_payload, ensure_ascii=False),
        encoding="utf-8",
    )

    hough = None
    if args.hough_report.is_file():
        previous = json.loads(args.hough_report.read_text(encoding="utf-8"))
        hough = {
            name: previous["datasets"][name]["hough"]
            for name in DATASET_NAMES
        }
        hough["overall"] = previous["overall"]["hough"]

    report = {
        "method": (
            "hybrid_v1: page thumbnail classifier + adaptive threshold/"
            "connected-edge ROI features + local Hough support"
        ),
        "random_seed": RANDOM_SEED,
        "split": {
            "train": "train_images2/test",
            "validation_and_threshold": "train_images3/test",
            "independent_test": "train_images4/test",
        },
        "threshold_rule": (
            "minimum validation FPR under recall >= 0.95; ties choose the "
            "highest threshold"
        ),
        "page_only_ablation": page_only,
        "hybrid_v1": hybrid,
        "candidate_recall": {
            name: _candidate_summary(dataset)
            for name, dataset in datasets.items()
        },
        "timing": {
            name: {
                "feature_seconds": dataset["feature_seconds"],
                "average_ms_per_page": (
                    dataset["feature_seconds"] * 1000
                    / len(dataset["labels"])
                ),
                "loaded_from_cache": dataset["from_cache"],
            }
            for name, dataset in datasets.items()
        },
        "previous_hough_baseline": hough,
        "model_output": str(args.model_output.resolve()),
        "limitations": [
            "The negative pages are generated no-seal counterparts and do "
            "not represent the full production negative distribution.",
            "The available split has no real document_id grouping.",
            "The benchmark measures page-level presence, not ROI IoU.",
            "The exported model is calibrated to these synthetic datasets "
            "and requires validation on real technology contracts.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "page_only_final_test": page_only["datasets"][
                    "train_images4"
                ]["metrics"],
                "hybrid_final_test": hybrid["datasets"]["train_images4"][
                    "metrics"
                ],
                "model_output": report["model_output"],
                "report": str(args.output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
