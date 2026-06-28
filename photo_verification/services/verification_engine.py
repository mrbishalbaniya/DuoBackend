"""Selfie verification orchestration."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import timedelta

from django.utils import timezone

from accounts.models import Profile
from photo_verification.constants import (
    FRAUD_REJECT,
    FRAUD_REVIEW,
    LIVENESS_PASS_THRESHOLD,
    SIMILARITY_REVIEW,
    SIMILARITY_VERIFIED,
    VERIFICATION_SESSION_TTL_MINUTES,
    VerificationStatus,
)
from photo_verification.models import UserVerification
from photo_verification.services.embedding_pipeline import (
    get_user_profile_embeddings,
    sync_embeddings_from_profile,
)
from photo_verification.services.face_matching import match_selfie_to_profile_embeddings
from photo_verification.services.fraud_detection import detect_verification_fraud
from photo_verification.services.image_utils import load_image_from_bytes
from photo_verification.services.liveness_detection import (
    aggregate_liveness_score,
    all_liveness_steps_passed,
)
from photo_verification.services.quality_analysis import analyze_quality
from photo_verification.services.face_detection import detect_faces
from photo_verification.ml.insightface_engine import extract_face_embedding


@dataclass
class VerificationResult:
    status: VerificationStatus
    similarity_score: float
    liveness_score: float
    fraud_probability: float
    verified_badge: bool
    rejection_reasons: list[str] = field(default_factory=list)


class VerificationEngine:
    def start_session(self, user) -> UserVerification:
        profile = user.profile
        sync_embeddings_from_profile(user)

        session = UserVerification.objects.create(
            user=user,
            session_token=uuid.uuid4(),
            profile_photo_url=profile.photo_url or "",
            verification_status=VerificationStatus.PENDING.value,
            expires_at=timezone.now() + timedelta(minutes=VERIFICATION_SESSION_TTL_MINUTES),
        )
        return session

    def get_active_session(self, user) -> UserVerification | None:
        return (
            UserVerification.objects.filter(
                user=user,
                verification_status=VerificationStatus.PENDING.value,
                expires_at__gt=timezone.now(),
            )
            .order_by("-created_at")
            .first()
        )

    def analyze_selfie_bytes(self, data: bytes) -> dict:
        loaded = load_image_from_bytes(data)
        faces = detect_faces(loaded.rgb)
        quality = analyze_quality(loaded.rgb, loaded.width, loaded.height)
        embedding = extract_face_embedding(loaded.rgb)
        fraud = detect_verification_fraud(loaded.rgb)

        return {
            "face_detected": faces.face_detected,
            "face_count": faces.face_count,
            "blur_score": quality.blur_score,
            "brightness_score": quality.brightness_score,
            "resolution_passed": quality.resolution_passed,
            "embedding": embedding.embedding,
            "fraud_probability": fraud.fraud_probability,
        }

    def complete_verification(
        self,
        session: UserVerification,
        selfie_data: bytes,
        selfie_url: str,
    ) -> VerificationResult:
        analysis = self.analyze_selfie_bytes(selfie_data)
        rejection_reasons: list[str] = []

        if not analysis["face_detected"]:
            rejection_reasons.append("No face detected in selfie.")
        if analysis["face_count"] > 1:
            rejection_reasons.append("Multiple faces detected in selfie.")
        if not analysis["resolution_passed"]:
            rejection_reasons.append("Selfie resolution too low.")
        if analysis["blur_score"] < 50:
            rejection_reasons.append("Selfie is too blurry.")

        liveness_score = aggregate_liveness_score(session.liveness_data or {})
        if not all_liveness_steps_passed(session.liveness_data or {}):
            rejection_reasons.append("Liveness challenges not completed.")

        fraud_probability = max(
            float(analysis["fraud_probability"]),
            float(session.fraud_probability or 0),
        )

        profile_embeddings = get_user_profile_embeddings(session.user)
        if not profile_embeddings:
            rejection_reasons.append("No profile photo embeddings found. Upload a clear profile photo first.")

        match = match_selfie_to_profile_embeddings(
            analysis["embedding"],
            profile_embeddings,
        )
        similarity_score = match.similarity_score

        session.selfie_photo_url = selfie_url
        session.similarity_score = similarity_score
        session.liveness_score = liveness_score
        session.fraud_probability = fraud_probability
        if match.best_profile_photo_url:
            session.profile_photo_url = match.best_profile_photo_url

        status, reasons = self._decide_status(
            similarity_score=similarity_score,
            liveness_score=liveness_score,
            fraud_probability=fraud_probability,
            rejection_reasons=rejection_reasons,
        )
        session.rejection_reasons = reasons
        session.verification_status = status.value

        verified_badge = status == VerificationStatus.VERIFIED
        if verified_badge:
            session.verified_at = timezone.now()
            Profile.objects.filter(user=session.user).update(is_verified=True)

        session.save()

        return VerificationResult(
            status=status,
            similarity_score=similarity_score,
            liveness_score=liveness_score,
            fraud_probability=fraud_probability,
            verified_badge=verified_badge,
            rejection_reasons=reasons,
        )

    def _decide_status(
        self,
        *,
        similarity_score: float,
        liveness_score: float,
        fraud_probability: float,
        rejection_reasons: list[str],
    ) -> tuple[VerificationStatus, list[str]]:
        reasons = list(rejection_reasons)

        if fraud_probability >= FRAUD_REJECT:
            reasons.append(f"High fraud risk ({fraud_probability:.0%}).")
            return VerificationStatus.REJECTED, reasons

        if similarity_score < SIMILARITY_REVIEW:
            reasons.append(f"Face match too low ({similarity_score:.0%}).")
            return VerificationStatus.REJECTED, reasons

        if reasons:
            return VerificationStatus.REJECTED, reasons

        if fraud_probability >= FRAUD_REVIEW:
            return VerificationStatus.UNDER_REVIEW, [
                f"Manual review required (fraud risk {fraud_probability:.0%})."
            ]

        if similarity_score < SIMILARITY_VERIFIED:
            return VerificationStatus.UNDER_REVIEW, [
                f"Manual review required (match {similarity_score:.0%})."
            ]

        if liveness_score < LIVENESS_PASS_THRESHOLD:
            return VerificationStatus.UNDER_REVIEW, [
                f"Liveness score borderline ({liveness_score:.0%})."
            ]

        return VerificationStatus.VERIFIED, []

    @staticmethod
    def admin_approve(session: UserVerification, notes: str = "") -> None:
        session.verification_status = VerificationStatus.VERIFIED.value
        session.verified_at = timezone.now()
        session.review_notes = notes
        session.save(update_fields=["verification_status", "verified_at", "review_notes", "updated_at"])
        Profile.objects.filter(user=session.user).update(is_verified=True)

    @staticmethod
    def admin_reject(session: UserVerification, notes: str = "") -> None:
        session.verification_status = VerificationStatus.REJECTED.value
        session.review_notes = notes
        session.rejection_reasons = session.rejection_reasons or []
        if notes:
            session.rejection_reasons = [*session.rejection_reasons, notes]
        session.save(
            update_fields=["verification_status", "review_notes", "rejection_reasons", "updated_at"]
        )
