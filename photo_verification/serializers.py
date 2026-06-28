from rest_framework import serializers

from photo_verification.models import PhotoAnalysis


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
