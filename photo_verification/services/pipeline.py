"""Orchestrates the full profile photo verification pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

from photo_verification.constants import PhotoStatus
from photo_verification.services.ai_detection import detect_ai_generated
from photo_verification.services.duplicate_detection import detect_duplicate
from photo_verification.services.face_detection import detect_faces
from photo_verification.services.image_utils import LoadedImage, load_image_from_file
from photo_verification.services.quality_analysis import analyze_quality
from photo_verification.services.scoring import ScoringResult, score_and_decide


@dataclass
class PhotoVerificationResult:
    face_detected: bool
    face_count: int
    face_centered: bool
    blur_score: float
    brightness_score: float
    resolution_passed: bool
    image_width: int
    image_height: int
    quality_score: int
    ai_generated_probability: float
    duplicate_probability: float
    status: PhotoStatus
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    image_hash: str = ""
    embedding: list[float] = field(default_factory=list)

    def to_analysis_dict(self) -> dict:
        return {
            "face_detected": self.face_detected,
            "face_count": self.face_count,
            "face_centered": self.face_centered,
            "blur_score": round(self.blur_score, 2),
            "brightness_score": round(self.brightness_score, 2),
            "resolution_passed": self.resolution_passed,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "quality_score": self.quality_score,
            "ai_generated_probability": round(self.ai_generated_probability, 4),
            "duplicate_probability": round(self.duplicate_probability, 4),
            "status": self.status.value,
            "warnings": self.warnings,
            "rejection_reasons": self.rejection_reasons,
        }


class PhotoVerificationPipeline:
    def analyze_bytes(self, data: bytes, *, user_id: int, is_primary: bool = False) -> PhotoVerificationResult:
        from photo_verification.services.image_utils import load_image_from_bytes

        loaded = load_image_from_bytes(data)
        return self._run(loaded, user_id=user_id, is_primary=is_primary)

    def analyze_file(self, uploaded_file, *, user_id: int, is_primary: bool = False) -> PhotoVerificationResult:
        loaded = load_image_from_file(uploaded_file)
        return self._run(loaded, user_id=user_id, is_primary=is_primary)

    def _run(self, loaded: LoadedImage, *, user_id: int, is_primary: bool) -> PhotoVerificationResult:
        face = detect_faces(loaded.rgb)
        quality = analyze_quality(loaded.rgb, loaded.width, loaded.height)
        ai = detect_ai_generated(
            loaded.rgb,
            face_boxes=face.face_boxes,
            exif=loaded.exif,
        )
        duplicate = detect_duplicate(
            hash_bits=loaded.hash_bits,
            face_embedding=face.embedding,
            user_id=user_id,
        )
        scored: ScoringResult = score_and_decide(
            face, quality, ai, duplicate, is_primary=is_primary
        )

        return PhotoVerificationResult(
            face_detected=face.face_detected,
            face_count=face.face_count,
            face_centered=face.face_centered,
            blur_score=quality.blur_score,
            brightness_score=quality.brightness_score,
            resolution_passed=quality.resolution_passed,
            image_width=quality.image_width,
            image_height=quality.image_height,
            quality_score=scored.quality_score,
            ai_generated_probability=ai.ai_generated_probability,
            duplicate_probability=duplicate.duplicate_probability,
            status=scored.status,
            warnings=scored.warnings,
            rejection_reasons=scored.rejection_reasons,
            image_hash=loaded.perceptual_hash,
            embedding=face.embedding,
        )
