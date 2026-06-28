"""Fraud signals for selfie verification (AI, screen replay, print)."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from photo_verification.services.ai_detection import detect_ai_generated


@dataclass(frozen=True)
class FraudDetectionResult:
    fraud_probability: float
    signals: dict[str, float]


def detect_verification_fraud(rgb: np.ndarray) -> FraudDetectionResult:
    ai = detect_ai_generated(rgb)
    screen = _screen_photo_score(rgb)
    print_score = _printed_photo_score(rgb)

    fraud = 0.45 * ai.ai_generated_probability + 0.30 * screen + 0.25 * print_score
    fraud = float(np.clip(fraud, 0.0, 1.0))

    return FraudDetectionResult(
        fraud_probability=fraud,
        signals={
            "ai_generated": ai.ai_generated_probability,
            "screen_replay": screen,
            "printed_photo": print_score,
        },
    )


def _screen_photo_score(rgb: np.ndarray) -> float:
    """Moiré / high-frequency grid patterns from photographing a screen."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    f = np.fft.fft2(gray)
    fshift = np.fft.fftshift(f)
    magnitude = np.log1p(np.abs(fshift))
    h, w = magnitude.shape
    cy, cx = h // 2, w // 2
    band = magnitude[cy - 2 : cy + 3, :].mean()
    center = magnitude[cy - 15 : cy + 15, cx - 15 : cx + 15].mean()
    ratio = float(band / (center + 1e-6))
    return float(np.clip((ratio - 1.1) * 0.8, 0, 0.85))


def _laplacian_variance(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if image.ndim == 3 else image
    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _printed_photo_score(rgb: np.ndarray) -> float:
    """Low micro-contrast and paper-like flat regions."""
    lap = _laplacian_variance(rgb)
    flatness = float(np.clip(1.0 - lap / 180.0, 0, 1))
    color_std = float(np.std(rgb.astype(np.float32), axis=(0, 1)).mean())
    low_color = float(np.clip(1.0 - color_std / 45.0, 0, 1))
    return float(np.clip(0.6 * flatness + 0.4 * low_color, 0, 0.8))
