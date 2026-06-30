"""
AI-generated image detection for profile photos.

Combines face-region heuristics, metadata checks, and an optional PyTorch
classifier (PHOTO_AI_MODEL_PATH) tuned for portrait / selfie uploads.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from photo_verification.ml.ai_classifier import get_ai_classifier
from photo_verification.services.image_utils import ExifSignals

# Signal weights — tuned for portrait photos (face region weighted higher).
_SIGNAL_WEIGHTS: dict[str, float] = {
    "noise_deficit": 0.16,
    "texture_uniformity": 0.14,
    "dct_homogeneity": 0.12,
    "gradient_entropy_deficit": 0.10,
    "chrominance_uniformity": 0.12,
    "highlight_regularity": 0.08,
    "color_banding": 0.08,
    "channel_correlation": 0.06,
    "exif_suspicion": 0.14,
}


@dataclass(frozen=True)
class AiDetectionResult:
    ai_generated_probability: float
    signals: dict[str, float]


def detect_ai_generated(
    rgb: np.ndarray,
    *,
    face_boxes: list[tuple[int, int, int, int]] | None = None,
    exif: ExifSignals | None = None,
) -> AiDetectionResult:
    face_region = _crop_primary_face(rgb, face_boxes)
    face_signals = _analyze_region(face_region)
    full_signals = _analyze_region(rgb)

    # Portrait photos: prioritize the face crop; full frame adds context.
    blended: dict[str, float] = {}
    for key in _SIGNAL_WEIGHTS:
        if key == "exif_suspicion":
            blended[key] = _exif_suspicion_score(exif)
            continue
        face_val = face_signals.get(key, 0.0)
        full_val = full_signals.get(key, 0.0)
        blended[key] = float(0.78 * face_val + 0.22 * full_val)

    heuristic = _ensemble_probability(blended, exif=exif)

    classifier = get_ai_classifier()
    model_score = classifier.predict(face_region) if classifier else None

    if model_score is not None:
        probability = 0.58 * model_score + 0.42 * heuristic
    else:
        probability = heuristic

    probability = float(np.clip(probability, 0.0, 1.0))
    signals = {**blended, "heuristic": heuristic, "model": model_score or 0.0}
    return AiDetectionResult(ai_generated_probability=probability, signals=signals)


def _crop_primary_face(
    rgb: np.ndarray,
    face_boxes: list[tuple[int, int, int, int]] | None,
) -> np.ndarray:
    if not face_boxes:
        return rgb

    x1, y1, x2, y2 = max(face_boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    w, h = x2 - x1, y2 - y1
    pad_x = int(w * 0.22)
    pad_y = int(h * 0.28)
    ih, iw = rgb.shape[:2]
    fx1 = max(0, x1 - pad_x)
    fy1 = max(0, y1 - pad_y)
    fx2 = min(iw, x2 + pad_x)
    fy2 = min(ih, y2 + pad_y)
    crop = rgb[fy1:fy2, fx1:fx2]
    return crop if crop.size else rgb


def _analyze_region(region: np.ndarray) -> dict[str, float]:
    if region.size == 0 or min(region.shape[:2]) < 32:
        return {key: 0.0 for key in _SIGNAL_WEIGHTS if key != "exif_suspicion"}

    gray = cv2.cvtColor(region, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    return {
        "noise_deficit": _noise_deficit_score(gray),
        "texture_uniformity": _texture_uniformity_score(gray),
        "dct_homogeneity": _dct_homogeneity_score(gray),
        "gradient_entropy_deficit": _gradient_entropy_deficit_score(gray),
        "chrominance_uniformity": _chrominance_uniformity_score(region),
        "highlight_regularity": _highlight_regularity_score(region),
        "color_banding": _color_banding_score(region),
        "channel_correlation": _channel_correlation_score(region),
    }


def _ensemble_probability(signals: dict[str, float], *, exif: ExifSignals | None) -> float:
    weighted = sum(signals[k] * _SIGNAL_WEIGHTS[k] for k in _SIGNAL_WEIGHTS)
    strong_hits = sum(1 for k, v in signals.items() if k in _SIGNAL_WEIGHTS and v >= 0.58)

    if strong_hits >= 4:
        weighted = min(1.0, weighted * 1.12 + 0.06)
    elif strong_hits <= 1:
        weighted *= 0.82

    natural_noise = 1.0 - signals.get("noise_deficit", 0.5)
    natural_texture = 1.0 - signals.get("texture_uniformity", 0.5)
    exif_trust = exif.trust_score if exif else 0.15

    if natural_noise >= 0.55 and natural_texture >= 0.50 and exif_trust >= 0.55:
        weighted *= 0.45
    elif natural_noise >= 0.62 and natural_texture >= 0.55:
        weighted *= 0.62
    elif exif_trust >= 0.70:
        weighted *= 0.75

    if exif and exif.ai_software_hint:
        weighted = max(weighted, 0.92)

    return float(np.clip(weighted, 0.0, 0.98))


def _exif_suspicion_score(exif: ExifSignals | None) -> float:
    if exif is None:
        return 0.35
    if exif.ai_software_hint:
        return 0.98
    if exif.trust_score >= 0.70:
        return 0.08
    if exif.trust_score >= 0.45:
        return 0.22
    return 0.48


def _noise_deficit_score(gray: np.ndarray) -> float:
    """Synthetic portraits often lack fine sensor noise in mid/high frequencies."""
    h, w = gray.shape
    f = np.fft.fft2(gray)
    fshift = np.fft.fftshift(f)
    magnitude = np.abs(fshift)
    cy, cx = h // 2, w // 2
    y, x = np.ogrid[:h, :w]
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    radius = min(h, w) * 0.15

    low = magnitude[dist < radius].mean()
    mid = magnitude[(dist >= radius) & (dist < radius * 2.2)].mean()
    high = magnitude[dist >= radius * 2.2].mean()

    mid_ratio = float(mid / (low + 1e-6))
    high_ratio = float(high / (low + 1e-6))

    residual = gray - cv2.GaussianBlur(gray, (0, 0), 0.8)
    noise_std = float(np.std(residual))

    mid_signal = float(np.clip((0.42 - mid_ratio) * 2.0, 0, 1))
    high_signal = float(np.clip((0.18 - high_ratio) * 4.0, 0, 1))
    noise_signal = float(np.clip(1.0 - noise_std * 18.0, 0, 1))

    return float(np.clip(0.40 * mid_signal + 0.35 * high_signal + 0.25 * noise_signal, 0, 1))


def _texture_uniformity_score(gray: np.ndarray) -> float:
    """Over-smoothed AI skin shows low local binary pattern diversity."""
    small = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA)
    uint = (small * 255).astype(np.uint8)
    lbp = _local_binary_pattern(uint)
    hist, _ = np.histogram(lbp.ravel(), bins=256, range=(0, 256), density=True)
    hist = hist[hist > 0]
    entropy = float(-(hist * np.log2(hist)).sum())
    max_entropy = 8.0
    return float(np.clip(1.0 - entropy / max_entropy, 0, 1))


def _local_binary_pattern(gray: np.uint8) -> np.ndarray:
    padded = cv2.copyMakeBorder(gray, 1, 1, 1, 1, cv2.BORDER_REFLECT_101)
    center = padded[1:-1, 1:-1]
    code = np.zeros_like(center, dtype=np.uint8)
    offsets = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]
    for bit, (dy, dx) in enumerate(offsets):
        neighbor = padded[1 + dy : 1 + dy + center.shape[0], 1 + dx : 1 + dx + center.shape[1]]
        code |= ((neighbor >= center).astype(np.uint8) << bit)
    return code


def _dct_homogeneity_score(gray: np.ndarray) -> float:
    """GAN/diffusion outputs often have unusually uniform 8x8 DCT blocks."""
    resized = cv2.resize(gray, (256, 256), interpolation=cv2.INTER_AREA)
    uint = (resized * 255).astype(np.float32)
    h, w = uint.shape
    ac_vars: list[float] = []

    for y in range(0, h - 8, 8):
        for x in range(0, w - 8, 8):
            block = uint[y : y + 8, x : x + 8]
            dct = cv2.dct(block)
            ac = dct.copy()
            ac[0, 0] = 0
            ac_vars.append(float(np.var(ac)))

    if not ac_vars:
        return 0.0

    block_std = float(np.std(ac_vars))
    mean_var = float(np.mean(ac_vars))
    homogeneity = float(np.clip(1.0 - block_std * 2.2, 0, 1))
    low_ac = float(np.clip(1.0 - mean_var / 120.0, 0, 1))
    return float(np.clip(0.55 * homogeneity + 0.45 * low_ac, 0, 1))


def _gradient_entropy_deficit_score(gray: np.ndarray) -> float:
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx**2 + gy**2)
    mag = (mag / (mag.max() + 1e-6) * 255).astype(np.uint8)
    hist, _ = np.histogram(mag.ravel(), bins=64, range=(0, 256), density=True)
    hist = hist[hist > 0]
    entropy = float(-(hist * np.log2(hist)).sum())
    return float(np.clip(1.0 - entropy / 5.8, 0, 1))


def _chrominance_uniformity_score(rgb: np.ndarray) -> float:
    """AI skin tones cluster tightly in LAB chrominance channels."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    a_std = float(np.std(lab[..., 1]))
    b_std = float(np.std(lab[..., 2]))
    chroma_std = (a_std + b_std) / 2.0
    skin_mask = _skin_mask(rgb)
    if skin_mask.any():
        skin_lab = lab[skin_mask]
        skin_chroma = float((np.std(skin_lab[:, 1]) + np.std(skin_lab[:, 2])) / 2.0)
        chroma_std = 0.65 * skin_chroma + 0.35 * chroma_std

    return float(np.clip(1.0 - chroma_std / 22.0, 0, 1))


def _skin_mask(rgb: np.ndarray) -> np.ndarray:
    ycrcb = cv2.cvtColor(rgb, cv2.COLOR_RGB2YCrCb)
    cr = ycrcb[..., 1]
    cb = ycrcb[..., 2]
    return (cr >= 133) & (cr <= 173) & (cb >= 77) & (cb <= 127)


def _highlight_regularity_score(rgb: np.ndarray) -> float:
    """Specular highlights on AI faces are often too symmetric / blob-like."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    _, bright = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY)
    bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 0.0

    areas = [cv2.contourArea(c) for c in contours if cv2.contourArea(c) > 12]
    if not areas:
        return 0.0

    circularities: list[float] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 12:
            continue
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        circularities.append(float(4 * np.pi * area / (perimeter**2)))

    if not circularities:
        return 0.0

    mean_circ = float(np.mean(circularities))
    area_cv = float(np.std(areas) / (np.mean(areas) + 1e-6))
    circ_signal = float(np.clip((mean_circ - 0.55) * 2.0, 0, 1))
    uniform_signal = float(np.clip(1.0 - area_cv, 0, 1))
    return float(np.clip(0.6 * circ_signal + 0.4 * uniform_signal, 0, 1))


def _color_banding_score(rgb: np.ndarray) -> float:
    """Posterized gradients / banding common in diffusion upscales."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    channel = lab[..., 0]
    smooth = cv2.GaussianBlur(channel, (0, 0), 2.5)
    grad = np.abs(cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3))
    grad = grad[grad > 0.5]
    if grad.size == 0:
        return 0.0

    hist, _ = np.histogram(grad.ravel(), bins=48, range=(0, float(grad.max()) + 1e-6))
    peaks = int(np.sum(hist > hist.max() * 0.35))
    peak_ratio = peaks / len(hist)
    return float(np.clip((0.22 - peak_ratio) * 4.0 + 0.35, 0, 1))


def _channel_correlation_score(rgb: np.ndarray) -> float:
    """Unnatural global RGB coupling in synthetic portraits."""
    r = rgb[..., 0].astype(np.float32).ravel()
    g = rgb[..., 1].astype(np.float32).ravel()
    b = rgb[..., 2].astype(np.float32).ravel()
    if np.std(r) < 1e-3 or np.std(g) < 1e-3:
        return 0.0

    rg = float(np.corrcoef(r, g)[0, 1])
    rb = float(np.corrcoef(r, b)[0, 1])
    gb = float(np.corrcoef(g, b)[0, 1])
    avg = (abs(rg) + abs(rb) + abs(gb)) / 3.0
    return float(np.clip((avg - 0.82) * 3.5, 0, 1))
