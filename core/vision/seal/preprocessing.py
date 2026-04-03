from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt

ImageArray = npt.NDArray[np.uint8]
MaskArray = npt.NDArray[np.uint8]

# 红色在 HSV 中跨越 0 度，因此拆成两段范围。
# 当前版本只把红色区域当作“定位印章”的线索，最终结果仍然使用原图裁剪。
LOWER_RED_1 = np.array([0, 45, 10], dtype=np.uint8)
UPPER_RED_1 = np.array([14, 255, 255], dtype=np.uint8)
LOWER_RED_2 = np.array([166, 45, 10], dtype=np.uint8)
UPPER_RED_2 = np.array([180, 255, 255], dtype=np.uint8)


def load_image(image_path: str | Path) -> ImageArray:
    """读取原始图片，返回 BGR 三通道图像矩阵。"""
    path = Path(image_path)
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"failed to load image: {path}")
    return image


def build_red_mask(image: ImageArray) -> MaskArray:
    """从原图中提取红色区域二值图。"""
    if image is None:
        raise ValueError("image must not be None")
    if len(image.shape) != 3 or image.shape[2] != 3:
        raise ValueError("image must be a BGR color image with shape (H, W, 3)")

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask_1 = cv2.inRange(hsv, LOWER_RED_1, UPPER_RED_1)
    mask_2 = cv2.inRange(hsv, LOWER_RED_2, UPPER_RED_2)
    return cv2.bitwise_or(mask_1, mask_2)


def clean_red_mask(mask: MaskArray) -> MaskArray:
    """对红色区域做轻量去噪，供后续定位印章边界使用。"""
    if mask is None:
        raise ValueError("mask must not be None")
    if len(mask.shape) != 2:
        raise ValueError("mask must be a single-channel binary image")

    kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    kernel_medium = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_small, iterations=2)
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel_medium, iterations=2)
    return closed


def crop_bbox(image: ImageArray, x: int, y: int, width: int, height: int) -> ImageArray:
    """按给定外接框从原图裁出局部图像。"""
    if image is None:
        raise ValueError("image must not be None")
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")

    image_height, image_width = image.shape[:2]
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(image_width, x + width)
    y2 = min(image_height, y + height)

    if x1 >= x2 or y1 >= y2:
        raise ValueError("invalid crop bbox after clipping")

    return image[y1:y2, x1:x2]


def enhance_seal_crop(crop_image: ImageArray) -> ImageArray:
    """当前版本不做额外增强，直接返回原图裁剪副本。"""
    if crop_image is None:
        raise ValueError("crop_image must not be None")
    if len(crop_image.shape) != 3 or crop_image.shape[2] != 3:
        raise ValueError("crop_image must be a BGR color image with shape (H, W, 3)")

    return crop_image.copy()
