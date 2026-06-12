from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt

from .models import SealBBox

ImageArray = npt.NDArray[np.uint8]
FeatureArray = npt.NDArray[np.float64]

MODEL_PATH = (
    Path(__file__).resolve().parents[4]
    / "models"
    / "seal_hybrid_v1.json"
)
RESIZE_LONG_SIDE = 1024
THUMBNAIL_SIZE = (32, 45)
MAX_CANDIDATES = 8
CANDIDATE_FEATURE_COUNT = 12


@dataclass(slots=True)
class HybridSealCandidate:
    bbox: SealBBox
    score: float
    features: list[float]


@dataclass(slots=True)
class HybridSealDecision:
    has_seal: bool
    score: float
    candidates: list[HybridSealCandidate]


@dataclass(slots=True)
class HybridSealModel:
    mean: FeatureArray
    scale: FeatureArray
    weights: FeatureArray
    intercept: float
    threshold: float

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> HybridSealModel:
        return cls(
            mean=np.asarray(payload["mean"], dtype=np.float64),
            scale=np.asarray(payload["scale"], dtype=np.float64),
            weights=np.asarray(payload["weights"], dtype=np.float64),
            intercept=float(payload["intercept"]),
            threshold=float(payload["threshold"]),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "mean": self.mean.tolist(),
            "scale": self.scale.tolist(),
            "weights": self.weights.tolist(),
            "intercept": self.intercept,
            "threshold": self.threshold,
        }

    def predict_score(self, features: FeatureArray) -> float:
        normalized = (features - self.mean) / self.scale
        logit = float(normalized @ self.weights + self.intercept)
        return 1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, logit))))


def _resize_page(image: ImageArray) -> tuple[ImageArray, float]:
    height, width = image.shape[:2]
    scale = min(1.0, RESIZE_LONG_SIDE / max(height, width))
    if scale == 1.0:
        return image.copy(), scale
    resized = cv2.resize(
        image,
        None,
        fx=scale,
        fy=scale,
        interpolation=cv2.INTER_AREA,
    )
    return resized, scale


def _iou(left: SealBBox, right: SealBBox) -> float:
    lx, ly, lw, lh = left
    rx, ry, rw, rh = right
    intersection_width = max(0, min(lx + lw, rx + rw) - max(lx, rx))
    intersection_height = max(0, min(ly + lh, ry + rh) - max(ly, ry))
    intersection = intersection_width * intersection_height
    union = lw * lh + rw * rh - intersection
    return intersection / union if union else 0.0


def _ring_density(mask: npt.NDArray[np.uint8]) -> float:
    height, width = mask.shape
    border = max(2, int(round(min(height, width) * 0.16)))
    ring = np.ones(mask.shape, dtype=bool)
    if height > border * 2 and width > border * 2:
        ring[border:-border, border:-border] = False
    return float(np.mean(mask[ring] > 0))


def _local_circle_support(gray: npt.NDArray[np.uint8]) -> float:
    side = max(gray.shape)
    scale = min(1.0, 128 / side)
    sample = cv2.resize(
        gray,
        None,
        fx=scale,
        fy=scale,
        interpolation=cv2.INTER_AREA,
    )
    sample = cv2.GaussianBlur(sample, (5, 5), 1.0)
    minimum_side = min(sample.shape)
    circles = cv2.HoughCircles(
        sample,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(12, minimum_side // 3),
        param1=100,
        param2=18,
        minRadius=max(6, int(minimum_side * 0.18)),
        maxRadius=max(8, int(minimum_side * 0.52)),
    )
    return float(circles is not None)


def _candidate_features(
    gray: npt.NDArray[np.uint8],
    binary: npt.NDArray[np.uint8],
    edges: npt.NDArray[np.uint8],
    contour: npt.NDArray[np.int32],
    bbox: SealBBox,
) -> list[float]:
    x, y, width, height = bbox
    roi_gray = gray[y : y + height, x : x + width]
    roi_binary = binary[y : y + height, x : x + width]
    roi_edges = edges[y : y + height, x : x + width]
    bbox_area = width * height
    page_area = gray.shape[0] * gray.shape[1]
    contour_area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)
    circularity = (
        4.0 * math.pi * contour_area / (perimeter * perimeter)
        if perimeter
        else 0.0
    )
    hull_area = cv2.contourArea(cv2.convexHull(contour))
    solidity = contour_area / hull_area if hull_area else 0.0
    aspect_score = min(width, height) / max(width, height)
    components = cv2.connectedComponents(
        (roi_binary > 0).astype(np.uint8),
        connectivity=8,
    )[0] - 1
    return [
        bbox_area / page_area,
        aspect_score,
        min(1.0, circularity),
        min(1.0, solidity),
        contour_area / bbox_area,
        float(np.mean(roi_edges > 0)),
        float(np.mean(roi_binary > 0)),
        _ring_density(roi_binary),
        min(1.0, components / 40.0),
        float(np.std(roi_gray) / 128.0),
        _local_circle_support(roi_gray),
        1.0 - abs(
            (x + width / 2) / gray.shape[1] - 0.5
        ),
    ]


def _candidate_score(features: list[float]) -> float:
    (
        area_ratio,
        aspect,
        circularity,
        solidity,
        extent,
        edge_density,
        ink_density,
        ring_density,
        component_density,
        contrast,
        circle_support,
        _,
    ) = features
    size_score = math.exp(-abs(math.log(max(area_ratio, 1e-6) / 0.008)))
    texture_score = min(1.0, edge_density * 5.0 + contrast * 0.5)
    structure_score = min(
        1.0,
        ring_density * 2.0 + component_density * 0.4 + circle_support * 0.5,
    )
    return (
        size_score * 0.18
        + aspect * 0.14
        + circularity * 0.10
        + solidity * 0.06
        + extent * 0.05
        + texture_score * 0.20
        + structure_score * 0.27
        + min(1.0, ink_density * 2.5) * 0.05
    )


def recall_seal_candidates(image: ImageArray) -> list[HybridSealCandidate]:
    resized, resize_scale = _resize_page(image)
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
        31,
        11,
    )
    edges = cv2.Canny(enhanced, 40, 120)
    masks = [
        cv2.morphologyEx(
            binary,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
            iterations=2,
        ),
        cv2.morphologyEx(
            edges,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)),
            iterations=2,
        ),
    ]

    page_area = gray.shape[0] * gray.shape[1]
    raw_candidates: list[HybridSealCandidate] = []
    for mask in masks:
        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_LIST,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            bbox_area_ratio = width * height / page_area
            if not 0.00025 <= bbox_area_ratio <= 0.05:
                continue
            if min(width, height) < 18 or max(width, height) / min(width, height) > 3.5:
                continue
            bbox = [x, y, width, height]
            features = _candidate_features(
                enhanced,
                binary,
                edges,
                contour,
                bbox,
            )
            score = _candidate_score(features)
            if score < 0.28:
                continue
            original_bbox = [
                int(round(x / resize_scale)),
                int(round(y / resize_scale)),
                int(round(width / resize_scale)),
                int(round(height / resize_scale)),
            ]
            raw_candidates.append(
                HybridSealCandidate(
                    bbox=original_bbox,
                    score=score,
                    features=features,
                )
            )

    kept: list[HybridSealCandidate] = []
    for candidate in sorted(
        raw_candidates,
        key=lambda item: item.score,
        reverse=True,
    ):
        if all(_iou(candidate.bbox, item.bbox) < 0.35 for item in kept):
            kept.append(candidate)
        if len(kept) == MAX_CANDIDATES:
            break
    return kept


def extract_page_features(
    image: ImageArray,
) -> tuple[FeatureArray, list[HybridSealCandidate]]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    thumbnail = cv2.resize(
        gray,
        THUMBNAIL_SIZE,
        interpolation=cv2.INTER_AREA,
    ).astype(np.float64) / 255.0
    gradient_x = cv2.Sobel(thumbnail, cv2.CV_64F, 1, 0, ksize=3)
    gradient_y = cv2.Sobel(thumbnail, cv2.CV_64F, 0, 1, ksize=3)
    gradient = cv2.magnitude(gradient_x, gradient_y)
    candidates = recall_seal_candidates(image)

    candidate_features: list[float] = []
    for candidate in candidates:
        candidate_features.extend(candidate.features)
    candidate_features.extend(
        [0.0]
        * (
            (MAX_CANDIDATES - len(candidates))
            * CANDIDATE_FEATURE_COUNT
        )
    )
    summary = [
        float(np.mean(thumbnail)),
        float(np.std(thumbnail)),
        float(np.mean(gradient)),
        float(np.std(gradient)),
        len(candidates) / MAX_CANDIDATES,
        max((candidate.score for candidate in candidates), default=0.0),
        float(np.mean([item.score for item in candidates]))
        if candidates
        else 0.0,
    ]
    features = np.concatenate(
        (
            thumbnail.ravel(),
            gradient.ravel(),
            np.asarray(summary, dtype=np.float64),
            np.asarray(candidate_features, dtype=np.float64),
        )
    )
    return features, candidates


@lru_cache(maxsize=1)
def load_hybrid_model(model_path: str | Path = MODEL_PATH) -> HybridSealModel:
    payload = json.loads(Path(model_path).read_text(encoding="utf-8"))
    return HybridSealModel.from_dict(payload)


def detect_page_seal(
    image: ImageArray,
    model: HybridSealModel | None = None,
) -> HybridSealDecision:
    features, candidates = extract_page_features(image)
    classifier = model or load_hybrid_model()
    score = classifier.predict_score(features)
    return HybridSealDecision(
        has_seal=score >= classifier.threshold,
        score=score,
        candidates=candidates,
    )
