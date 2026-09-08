from django.conf import settings
from django.db import models

from .constants import ModerationStatus, PhotoStatus, RejectionCategory, VerificationStatus


class PhotoAnalysis(models.Model):
    """Stores AI verification results for an uploaded profile image."""

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Photo analyses"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["user", "image_hash"], name="photo_user_hash_idx"),
        ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="photo_analyses",
    )
    image_url = models.URLField(max_length=1000, blank=True)
    image_hash = models.CharField(max_length=64, blank=True, db_index=True)
    embedding = models.JSONField(default=list, blank=True)

    face_detected = models.BooleanField(default=False)
    face_count = models.PositiveSmallIntegerField(default=0)
    face_centered = models.BooleanField(default=False)

    blur_score = models.FloatField(default=0.0)
    brightness_score = models.FloatField(default=0.0)
    resolution_passed = models.BooleanField(default=False)
    image_width = models.PositiveIntegerField(default=0)
    image_height = models.PositiveIntegerField(default=0)

    quality_score = models.PositiveSmallIntegerField(default=0)
    ai_generated_probability = models.FloatField(default=0.0)
    duplicate_probability = models.FloatField(default=0.0)

    status = models.CharField(
        max_length=16,
        choices=[(s.value, s.value) for s in PhotoStatus],
        default=PhotoStatus.REJECTED,
    )
    warnings = models.JSONField(default=list, blank=True)
    rejection_reasons = models.JSONField(default=list, blank=True)
    is_primary = models.BooleanField(
        default=False,
        help_text="Whether this was uploaded as the primary profile photo.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"PhotoAnalysis #{self.pk} user={self.user_id} {self.status}"


class ProfilePhoto(models.Model):
    """The real per-photo record: identity, order, and — critically — the
    moderation status that gates whether a photo may ever be shown to other
    users. `Profile.photo_url`/`photo_urls` (accounts app) may only ever be
    set to URLs backed by an APPROVED row here (enforced in
    accounts.ProfileSerializer.validate); every discovery/matching/chat
    surface already reads those fields unconditionally, so this is the single
    enforcement point that makes them safe.
    """

    class Meta:
        ordering = ["order", "uploaded_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "order"]),
            models.Index(fields=["url"]),
        ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile_photos",
    )
    url = models.URLField(max_length=1000)
    status = models.CharField(
        max_length=16,
        choices=[(s.value, s.value) for s in ModerationStatus],
        default=ModerationStatus.PENDING,
    )
    rejection_reason = models.CharField(
        max_length=200,
        blank=True,
        help_text="User-facing, friendly reason only — never a raw category or score.",
    )
    rejection_category = models.CharField(
        max_length=32,
        choices=[(c.value, c.value) for c in RejectionCategory],
        blank=True,
        help_text="Internal-only classification. Never exposed via the API.",
    )
    moderation_source = models.CharField(
        max_length=64,
        blank=True,
        help_text='e.g. "nudenet+clip+quality_pipeline" or "manual:<username>".',
    )
    moderated_at = models.DateTimeField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    photo_analysis = models.ForeignKey(
        PhotoAnalysis,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profile_photos",
        help_text="Quality/face/duplicate signals for this upload (reused, not duplicated).",
    )

    def __str__(self) -> str:
        return f"ProfilePhoto #{self.pk} user={self.user_id} {self.status}"


class FaceEmbedding(models.Model):
    """InsightFace (or fallback) embedding for a profile photo."""

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="face_embeddings",
    )
    photo_url = models.URLField(max_length=1000)
    photo_analysis = models.ForeignKey(
        PhotoAnalysis,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="face_embeddings",
    )
    embedding_vector = models.JSONField(default=list)
    quality_score = models.PositiveSmallIntegerField(default=0)
    face_count = models.PositiveSmallIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"FaceEmbedding #{self.pk} user={self.user_id}"


class UserVerification(models.Model):
    """Selfie verification session and result."""

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["verification_status"]),
            models.Index(fields=["session_token"]),
        ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verifications",
    )
    session_token = models.UUIDField(unique=True, db_index=True)
    profile_photo_url = models.URLField(max_length=1000, blank=True)
    selfie_photo_url = models.URLField(max_length=1000, blank=True)

    similarity_score = models.FloatField(default=0.0)
    liveness_score = models.FloatField(default=0.0)
    fraud_probability = models.FloatField(default=0.0)

    verification_status = models.CharField(
        max_length=16,
        choices=[(s.value, s.value) for s in VerificationStatus],
        default=VerificationStatus.PENDING,
    )
    liveness_data = models.JSONField(default=dict, blank=True)
    rejection_reasons = models.JSONField(default=list, blank=True)
    review_notes = models.TextField(blank=True)

    verified_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"UserVerification #{self.pk} user={self.user_id} {self.verification_status}"
