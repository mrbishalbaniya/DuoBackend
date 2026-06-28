"""Blur, brightness, and resolution checks via OpenCV."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from photo_verification.constants import (
    BLUR_REJECT_THRESHOLD,
    BLUR_WARNING_THRESHOLD,
    BRIGHTNESS_HIGH_WARNING,
    BRIGHTNESS_LOW_WARNING,
    MIN_IMAGE_HEIGHT,
    MIN_IMAGE_WIDTH,
)


@dataclass(frozen=True)
class QualityAnalysisResult:
    blur_score: float
    brightness_score: float
    resolution_passed: bool
    image_width: int
    image_height: int
    is_very_blurry: bool
    is_slightly_blurry: bool
    is_too_dark: bool
    is_too_bright: bool


def analyze_quality(rgb: np.ndarray, width: int, height: int) -> QualityAnalysisResult:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    if gray.dtype != np.uint8:
        gray = gray.astype(np.uint8)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness_score = float(np.mean(gray))

    resolution_passed = width >= MIN_IMAGE_WIDTH and height >= MIN_IMAGE_HEIGHT
    is_very_blurry = blur_score < BLUR_REJECT_THRESHOLD
    is_slightly_blurry = (
        not is_very_blurry and blur_score < BLUR_WARNING_THRESHOLD
    )
    is_too_dark = brightness_score < BRIGHTNESS_LOW_WARNING
    is_too_bright = brightness_score > BRIGHTNESS_HIGH_WARNING

    return QualityAnalysisResult(
        blur_score=blur_score,
        brightness_score=brightness_score,
        resolution_passed=resolution_passed,
        image_width=width,
        image_height=height,
        is_very_blurry=is_very_blurry,
        is_slightly_blurry=is_slightly_blurry,
        is_too_dark=is_too_dark,
        is_too_bright=is_too_bright,
    )
