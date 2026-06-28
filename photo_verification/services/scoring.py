"""Aggregate verification signals into a 0–100 score and final status."""

from __future__ import annotations

from dataclasses import dataclass, field

from photo_verification.constants import (
    AI_FLAG_THRESHOLD,
    AI_REJECT_THRESHOLD,
    DUPLICATE_FLAG_THRESHOLD,
    DUPLICATE_REJECT_THRESHOLD,
    PhotoStatus,
    WEIGHT_CENTERED_FACE,
    WEIGHT_FACE_DETECTED,
    WEIGHT_GOOD_BRIGHTNESS,
    WEIGHT_GOOD_QUALITY,
    WEIGHT_GOOD_RESOLUTION,
    WEIGHT_SINGLE_FACE,
)
from photo_verification.services.ai_detection import AiDetectionResult
from photo_verification.services.duplicate_detection import DuplicateDetectionResult
from photo_verification.services.face_detection import FaceDetectionResult
from photo_verification.services.quality_analysis import QualityAnalysisResult


@dataclass
class ScoringResult:
    quality_score: int
    status: PhotoStatus
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)


def score_and_decide(
    face: FaceDetectionResult,
    quality: QualityAnalysisResult,
    ai: AiDetectionResult,
    duplicate: DuplicateDetectionResult,
    *,
    is_primary: bool,
) -> ScoringResult:
    warnings: list[str] = []
    rejections: list[str] = []
    points = 0

    if face.face_detected:
        points += WEIGHT_FACE_DETECTED
    else:
        rejections.append("No human face detected.")

    if face.face_count == 1:
        points += WEIGHT_SINGLE_FACE
    elif face.face_count > 1:
        msg = "Multiple faces detected in photo."
        if is_primary:
            warnings.append(msg)
        else:
            warnings.append(msg)

    if not quality.is_very_blurry and not quality.is_slightly_blurry:
        points += WEIGHT_GOOD_QUALITY
    elif quality.is_slightly_blurry:
        warnings.append("Image is slightly blurry.")
    else:
        rejections.append("Image is too blurry.")

    if not quality.is_too_dark and not quality.is_too_bright:
        points += WEIGHT_GOOD_BRIGHTNESS
    else:
        if quality.is_too_dark:
            warnings.append("Image is underexposed (too dark).")
        if quality.is_too_bright:
            warnings.append("Image is overexposed (too bright).")

    if quality.resolution_passed:
        points += WEIGHT_GOOD_RESOLUTION
    else:
        rejections.append(
            f"Resolution too low ({quality.image_width}×{quality.image_height}). "
            f"Minimum is 400×400 pixels."
        )

    if face.face_centered:
        points += WEIGHT_CENTERED_FACE
    elif face.face_detected:
        warnings.append("Face is not centered in the frame.")

    if ai.ai_generated_probability >= AI_REJECT_THRESHOLD:
        rejections.append(
            f"Image appears AI-generated (probability {ai.ai_generated_probability:.0%})."
        )
    elif ai.ai_generated_probability >= AI_FLAG_THRESHOLD:
        warnings.append(
            f"Image may be AI-generated (probability {ai.ai_generated_probability:.0%})."
        )

    if duplicate.duplicate_probability >= DUPLICATE_REJECT_THRESHOLD:
        rejections.append(
            f"Duplicate image detected (similarity {duplicate.duplicate_probability:.0%})."
        )
    elif duplicate.duplicate_probability >= DUPLICATE_FLAG_THRESHOLD:
        warnings.append(
            f"Image may be a duplicate (similarity {duplicate.duplicate_probability:.0%})."
        )

    quality_score = int(min(100, max(0, points)))

    if rejections:
        status = PhotoStatus.REJECTED
    elif warnings:
        status = PhotoStatus.WARNING
    else:
        status = PhotoStatus.APPROVED

    return ScoringResult(
        quality_score=quality_score,
        status=status,
        warnings=warnings,
        rejection_reasons=rejections,
    )
