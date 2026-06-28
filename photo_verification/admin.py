from django.contrib import admin, messages
from django.utils.html import format_html

from photo_verification.models import FaceEmbedding, PhotoAnalysis, UserVerification
from photo_verification.services.verification_engine import VerificationEngine


@admin.register(PhotoAnalysis)
class PhotoAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "status",
        "quality_score",
        "face_count",
        "ai_generated_probability",
        "duplicate_probability",
        "is_primary",
        "created_at",
    )
    list_filter = ("status", "face_detected", "resolution_passed", "is_primary")
    search_fields = ("user__username", "user__email", "image_url")
    readonly_fields = (
        "user",
        "image_url",
        "image_hash",
        "embedding",
        "face_detected",
        "face_count",
        "face_centered",
        "blur_score",
        "brightness_score",
        "resolution_passed",
        "image_width",
        "image_height",
        "quality_score",
        "ai_generated_probability",
        "duplicate_probability",
        "status",
        "warnings",
        "rejection_reasons",
        "created_at",
    )
    ordering = ("-created_at",)


@admin.register(FaceEmbedding)
class FaceEmbeddingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "is_primary", "face_count", "quality_score", "created_at")
    list_filter = ("is_primary",)
    search_fields = ("user__username", "photo_url")
    readonly_fields = ("embedding_vector", "created_at")


@admin.register(UserVerification)
class UserVerificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "verification_status",
        "similarity_score",
        "liveness_score",
        "fraud_probability",
        "verified_at",
        "created_at",
    )
    list_filter = ("verification_status",)
    search_fields = ("user__username", "user__email")
    readonly_fields = (
        "session_token",
        "similarity_score",
        "liveness_score",
        "fraud_probability",
        "liveness_data",
        "verified_at",
        "created_at",
        "updated_at",
        "profile_preview",
        "selfie_preview",
    )
    fieldsets = (
        (None, {"fields": ("user", "verification_status", "review_notes", "rejection_reasons")}),
        (
            "Scores",
            {"fields": ("similarity_score", "liveness_score", "fraud_probability")},
        ),
        (
            "Images",
            {"fields": ("profile_photo_url", "profile_preview", "selfie_photo_url", "selfie_preview")},
        ),
        ("Liveness", {"fields": ("liveness_data",)}),
        ("Meta", {"fields": ("session_token", "expires_at", "verified_at", "created_at", "updated_at")}),
    )
    actions = ["approve_verification", "reject_verification", "request_retake"]

    @admin.display(description="Profile")
    def profile_preview(self, obj: UserVerification):
        if not obj.profile_photo_url:
            return "—"
        return format_html('<img src="{}" style="max-height:120px;border-radius:8px;" />', obj.profile_photo_url)

    @admin.display(description="Selfie")
    def selfie_preview(self, obj: UserVerification):
        if not obj.selfie_photo_url:
            return "—"
        return format_html('<img src="{}" style="max-height:120px;border-radius:8px;" />', obj.selfie_photo_url)

    @admin.action(description="Approve — award verified badge")
    def approve_verification(self, request, queryset):
        for session in queryset:
            VerificationEngine.admin_approve(session, notes="Approved by admin")
        self.message_user(request, f"Approved {queryset.count()} verification(s).", messages.SUCCESS)

    @admin.action(description="Reject verification")
    def reject_verification(self, request, queryset):
        for session in queryset:
            VerificationEngine.admin_reject(session, notes="Rejected by admin")
        self.message_user(request, f"Rejected {queryset.count()} verification(s).", messages.WARNING)

    @admin.action(description="Request retake (reset to pending)")
    def request_retake(self, request, queryset):
        queryset.update(
            verification_status="PENDING",
            selfie_photo_url="",
            similarity_score=0,
            liveness_score=0,
            liveness_data={},
            rejection_reasons=["Please retake verification."],
        )
        self.message_user(request, "Marked for retake.", messages.INFO)
