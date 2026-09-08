"""Tests for the moderation decision logic — not the underlying models'
classification accuracy. We test with mocked ContentModerationResult/
ScoringResult inputs (never real explicit/violent imagery), matching the
project plan: verify thresholds, status mapping, and conservative-on-
uncertainty behavior, not train/eval the models themselves."""

from unittest.mock import patch

import numpy as np
from django.test import TestCase

from photo_verification.constants import ModerationStatus, PhotoStatus, RejectionCategory
from photo_verification.services import content_moderation
from photo_verification.services.content_moderation import ContentModerationResult, check_nsfw
from photo_verification.services.scoring import ScoringResult, decide_final_photo_status


def _quality(status=PhotoStatus.APPROVED, reasons=None):
    return ScoringResult(quality_score=90, status=status, warnings=[], rejection_reasons=reasons or [])


def _content(status=ModerationStatus.APPROVED, category=RejectionCategory.OTHER, reason=""):
    return ContentModerationResult(status=status, category=category, friendly_reason=reason)


class DecideFinalPhotoStatusTests(TestCase):
    def test_clean_quality_and_content_is_approved(self):
        decision = decide_final_photo_status(_quality(), _content())
        self.assertEqual(decision.status, ModerationStatus.APPROVED)
        self.assertEqual(decision.rejection_reason, "")

    def test_content_rejection_wins_even_with_good_quality(self):
        """A sharp, well-lit, correctly-centered photo that's still unsafe
        must never be approved just because quality signals look good."""
        decision = decide_final_photo_status(
            _quality(status=PhotoStatus.APPROVED),
            _content(status=ModerationStatus.REJECTED, category=RejectionCategory.NUDITY, reason="unsafe"),
        )
        self.assertEqual(decision.status, ModerationStatus.REJECTED)
        self.assertEqual(decision.rejection_category, RejectionCategory.NUDITY)
        self.assertEqual(decision.rejection_reason, "unsafe")

    def test_content_manual_review_wins_over_good_quality(self):
        decision = decide_final_photo_status(
            _quality(status=PhotoStatus.APPROVED),
            _content(status=ModerationStatus.MANUAL_REVIEW, category=RejectionCategory.VIOLENCE, reason="borderline"),
        )
        self.assertEqual(decision.status, ModerationStatus.MANUAL_REVIEW)
        self.assertEqual(decision.rejection_reason, "borderline")

    def test_quality_rejection_used_when_content_is_clean(self):
        decision = decide_final_photo_status(
            _quality(status=PhotoStatus.REJECTED, reasons=["Image is too blurry."]),
            _content(status=ModerationStatus.APPROVED),
        )
        self.assertEqual(decision.status, ModerationStatus.REJECTED)
        self.assertEqual(decision.rejection_category, RejectionCategory.QUALITY)
        self.assertIn("blurry", decision.rejection_reason)

    def test_quality_warning_is_still_approved(self):
        """PhotoStatus.WARNING (e.g. slightly blurry) is not a safety issue —
        preserves existing behavior where warned photos are still usable."""
        decision = decide_final_photo_status(
            _quality(status=PhotoStatus.WARNING),
            _content(status=ModerationStatus.APPROVED),
        )
        self.assertEqual(decision.status, ModerationStatus.APPROVED)

    def test_moderation_unavailable_never_silently_approves(self):
        """When a model fails to load/run, content_moderation.py returns
        MANUAL_REVIEW (fail closed) — confirm the combinator respects that
        rather than treating an unknown result as safe."""
        decision = decide_final_photo_status(
            _quality(status=PhotoStatus.APPROVED),
            _content(status=ModerationStatus.MANUAL_REVIEW, category=RejectionCategory.OTHER, reason="unavailable"),
        )
        self.assertNotEqual(decision.status, ModerationStatus.APPROVED)


class _FakeNudeDetector:
    def __init__(self, detections):
        self._detections = detections

    def detect(self, _jpeg_bytes):
        return self._detections


class CheckNsfwLabelPolicyTests(TestCase):
    """Tests the label->decision policy in check_nsfw against a mocked
    detector — never invokes the real ONNX model or any real imagery."""

    def _run(self, detections):
        with patch.object(content_moderation, "_get_nude_detector", return_value=_FakeNudeDetector(detections)):
            return check_nsfw(np.zeros((10, 10, 3), dtype=np.uint8))

    def test_no_detections_is_safe(self):
        self.assertEqual(self._run([]).status, ModerationStatus.APPROVED)

    def test_normal_swimwear_labels_are_safe(self):
        """DO NOT incorrectly reject: normal swimwear/beach/gym photos —
        BELLY/ARMPITS/FEET exposed and male shirtless are never flagged."""
        detections = [
            {"class": "BELLY_EXPOSED", "score": 0.95},
            {"class": "ARMPITS_EXPOSED", "score": 0.9},
            {"class": "FEET_EXPOSED", "score": 0.85},
            {"class": "MALE_BREAST_EXPOSED", "score": 0.99},
            {"class": "FACE_FEMALE", "score": 0.99},
        ]
        self.assertEqual(self._run(detections).status, ModerationStatus.APPROVED)

    def test_high_confidence_explicit_genitalia_is_rejected(self):
        detections = [{"class": "FEMALE_GENITALIA_EXPOSED", "score": 0.9}]
        result = self._run(detections)
        self.assertEqual(result.status, ModerationStatus.REJECTED)
        self.assertEqual(result.category, RejectionCategory.NUDITY)
        # Never expose the raw label/score to the user-facing reason.
        self.assertNotIn("FEMALE_GENITALIA_EXPOSED", result.friendly_reason)
        self.assertNotIn("0.9", result.friendly_reason)

    def test_low_confidence_explicit_label_goes_to_manual_review_not_reject(self):
        detections = [{"class": "MALE_GENITALIA_EXPOSED", "score": 0.4}]
        self.assertEqual(self._run(detections).status, ModerationStatus.MANUAL_REVIEW)

    def test_buttocks_or_breast_exposed_at_moderate_confidence_goes_to_review(self):
        """Context-dependent (thong swimwear etc.) at moderate confidence —
        a human decides rather than auto-rejecting a possible beach photo."""
        detections = [{"class": "BUTTOCKS_EXPOSED", "score": 0.5}]
        self.assertEqual(self._run(detections).status, ModerationStatus.MANUAL_REVIEW)

        detections = [{"class": "FEMALE_BREAST_EXPOSED", "score": 0.5}]
        self.assertEqual(self._run(detections).status, ModerationStatus.MANUAL_REVIEW)

    def test_buttocks_or_breast_exposed_at_very_high_confidence_auto_rejects(self):
        """At very high confidence this isn't ambiguous swimwear anymore —
        it should auto-reject rather than sit in manual review forever."""
        detections = [{"class": "BUTTOCKS_EXPOSED", "score": 0.9}]
        self.assertEqual(self._run(detections).status, ModerationStatus.REJECTED)

        detections = [{"class": "FEMALE_BREAST_EXPOSED", "score": 0.9}]
        self.assertEqual(self._run(detections).status, ModerationStatus.REJECTED)

    def test_detector_unavailable_routes_to_manual_review(self):
        with patch.object(content_moderation, "_get_nude_detector", return_value=None):
            result = check_nsfw(np.zeros((10, 10, 3), dtype=np.uint8))
        self.assertEqual(result.status, ModerationStatus.MANUAL_REVIEW)
