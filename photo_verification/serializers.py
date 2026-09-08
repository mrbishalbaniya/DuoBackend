from rest_framework import serializers

from photo_verification.models import PhotoAnalysis, ProfilePhoto


class PhotoAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhotoAnalysis
        fields = [
            "id",
            "image_url",
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
            "is_primary",
            "created_at",
        ]
        read_only_fields = fields


class PhotoUploadResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    image_url = serializers.URLField(required=False, allow_blank=True)
    analysis = PhotoAnalysisSerializer()
    detail = serializers.CharField(required=False, allow_blank=True)


class ProfilePhotoSerializer(serializers.ModelSerializer):
    """Public shape of a ProfilePhoto — deliberately excludes
    rejection_category and photo_analysis/moderation internals (confidence
    scores, model signals). Only a friendly rejection_reason is exposed."""

    class Meta:
        model = ProfilePhoto
        fields = [
            "id",
            "url",
            "status",
            "rejection_reason",
            "uploaded_at",
            "moderated_at",
            "order",
            "is_primary",
        ]
        read_only_fields = fields


class PhotoReorderSerializer(serializers.Serializer):
    photo_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False, max_length=5
    )
