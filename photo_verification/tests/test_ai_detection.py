"""Tests for AI-generated photo detection heuristics."""

from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image

from django.test import SimpleTestCase

from photo_verification.services.ai_detection import detect_ai_generated
from photo_verification.services.image_utils import ExifSignals, load_image_from_bytes


def _solid_portrait(size: int = 512) -> np.ndarray:
    rgb = np.zeros((size, size, 3), dtype=np.uint8)
    rgb[:, :] = (190, 150, 130)
    center = (size // 2, size // 2)
    cv2.ellipse(rgb, center, (size // 5, size // 4), 0, 0, 360, (220, 185, 165), -1)
    return rgb


def _natural_noisy_portrait(size: int = 512) -> np.ndarray:
    rng = np.random.default_rng(42)
    rgb = _solid_portrait(size).astype(np.float32)
    rgb += rng.normal(0, 8.0, rgb.shape)
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    sharp = cv2.addWeighted(gray, 1.4, cv2.GaussianBlur(gray, (0, 0), 1.0), -0.4, 0)
    rgb = cv2.cvtColor(sharp, cv2.COLOR_GRAY2RGB)
    return rgb


def _face_box(size: int = 512) -> list[tuple[int, int, int, int]]:
    margin = size // 4
    return [(margin, margin, size - margin, size - margin)]


class AiDetectionTests(SimpleTestCase):
    def test_smooth_synthetic_scores_higher_than_noisy_natural(self):
        smooth = detect_ai_generated(
            _solid_portrait(),
            face_boxes=_face_box(),
        )
        natural = detect_ai_generated(
            _natural_noisy_portrait(),
            face_boxes=_face_box(),
        )

        self.assertGreater(
            smooth.ai_generated_probability,
            natural.ai_generated_probability,
        )
        self.assertLess(natural.ai_generated_probability, 0.55)

    def test_trusted_camera_exif_reduces_probability(self):
        img = Image.new("RGB", (640, 640), color=(200, 160, 140))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", exif=img.getexif())
        loaded = load_image_from_bytes(buf.getvalue())

        trusted_exif = ExifSignals(
            has_camera_make=True,
            has_camera_model=True,
            has_datetime_original=True,
            software_tag="iPhone 15",
            ai_software_hint=False,
            trust_score=0.90,
        )
        no_exif = ExifSignals(
            has_camera_make=False,
            has_camera_model=False,
            has_datetime_original=False,
            software_tag="",
            ai_software_hint=False,
            trust_score=0.15,
        )

        with_exif = detect_ai_generated(
            loaded.rgb,
            face_boxes=[(160, 160, 480, 480)],
            exif=trusted_exif,
        )
        without_exif = detect_ai_generated(
            loaded.rgb,
            face_boxes=[(160, 160, 480, 480)],
            exif=no_exif,
        )

        self.assertLess(
            with_exif.ai_generated_probability,
            without_exif.ai_generated_probability,
        )

    def test_ai_software_exif_flags_high_probability(self):
        result = detect_ai_generated(
            _solid_portrait(),
            face_boxes=_face_box(),
            exif=ExifSignals(
                has_camera_make=False,
                has_camera_model=False,
                has_datetime_original=False,
                software_tag="Stable Diffusion XL",
                ai_software_hint=True,
                trust_score=0.05,
            ),
        )
        self.assertGreaterEqual(result.ai_generated_probability, 0.90)

    def test_signals_dict_includes_heuristic_breakdown(self):
        result = detect_ai_generated(_natural_noisy_portrait(), face_boxes=_face_box())
        self.assertIn("heuristic", result.signals)
        self.assertIn("noise_deficit", result.signals)
        self.assertIn("texture_uniformity", result.signals)
