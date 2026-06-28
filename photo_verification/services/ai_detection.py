"""
AI-generated image detection.

Uses heuristic signals today; swap in a PyTorch classifier via ml/ai_classifier.py
when a trained model is available (Stable Diffusion / Midjourney / Flux faces).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from photo_verification.ml.ai_classifier import get_ai_classifier


@dataclass(frozen=True)
class AiDetectionResult:
    ai_generated_probability: float
    signals: dict[str, float]


def detect_ai_generated(rgb: np.ndarray) -> AiDetectionResult:
    heuristic = _heuristic_ai_score(rgb)
    classifier = get_ai_classifier()
    model_score = classifier.predict(rgb) if classifier else None

    if model_score is not None:
        probability = 0.55 * model_score + 0.45 * heuristic
    else:
        probability = heuristic

    probability = float(np.clip(probability, 0.0, 1.0))
    return AiDetectionResult(
        ai_generated_probability=probability,
        signals={"heuristic": heuristic, "model": model_score or 0.0},
    )


def _heuristic_ai_score(rgb: np.ndarray) -> float:
    """Frequency + texture heuristics common in GAN/diffusion portraits."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    h, w = gray.shape

    # High-frequency energy ratio (synthetic faces often lack fine sensor noise)
    f = np.fft.fft2(gray)
    fshift = np.fft.fftshift(f)
    magnitude = np.abs(fshift)
    cy, cx = h // 2, w // 2
    y, x = np.ogrid[:h, :w]
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    inner = magnitude[dist < min(h, w) * 0.15].mean()
    outer = magnitude[dist >= min(h, w) * 0.15].mean()
    hf_ratio = float(outer / (inner + 1e-6))
    hf_signal = float(np.clip((0.35 - hf_ratio) * 2.5, 0, 1))

    # Local variance uniformity (over-smoothed skin)
    blur = cv2.GaussianBlur(gray, (0, 0), 1.2)
    residual = np.abs(gray - blur)
    var_map = cv2.blur(residual**2, (15, 15))
    smooth_signal = float(np.clip(1.0 - np.std(var_map) * 12, 0, 1))

    # Color channel correlation (unnatural skin tones)
    r, g, b = rgb[..., 0].astype(np.float32), rgb[..., 1].astype(np.float32), rgb[..., 2].astype(np.float32)
    if np.std(r) < 1e-3 or np.std(g) < 1e-3:
        corr_signal = 0.0
    else:
        rg = np.corrcoef(r.flatten(), g.flatten())[0, 1]
        rb = np.corrcoef(r.flatten(), b.flatten())[0, 1]
        corr_signal = float(np.clip((abs(rg) + abs(rb) - 1.4) * 0.8, 0, 1))

    score = 0.4 * hf_signal + 0.35 * smooth_signal + 0.25 * corr_signal
    return float(np.clip(score, 0.05, 0.85))
