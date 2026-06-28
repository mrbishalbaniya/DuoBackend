from rest_framework import serializers

from photo_verification.constants import LIVENESS_STEPS
from photo_verification.models import FaceEmbedding, UserVerification


class FaceEmbeddingSerializer(serializers.ModelSerializer):
    class Meta:
        model = FaceEmbedding
        fields = [
            "id",
            "photo_url",
            "quality_score",
            "face_count",
            "is_primary",
            "created_at",
        ]
        read_only_fields = fields


class UserVerificationSerializer(serializers.ModelSerializer):
    verified_badge = serializers.SerializerMethodField()
    liveness_steps_completed = serializers.SerializerMethodField()

    class Meta:
        model = UserVerification
        fields = [
            "id",
            "session_token",
            "profile_photo_url",
            "selfie_photo_url",
            "similarity_score",
            "liveness_score",
            "fraud_probability",
            "verification_status",
            "liveness_data",
            "liveness_steps_completed",
            "rejection_reasons",
            "review_notes",
            "verified_badge",
            "verified_at",
            "expires_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_verified_badge(self, obj: UserVerification) -> bool:
        return obj.verification_status == "VERIFIED"

    def get_liveness_steps_completed(self, obj: UserVerification) -> list[str]:
        data = obj.liveness_data or {}
        return [step for step in LIVENESS_STEPS if data.get(step, {}).get("passed")]


class VerificationStatusResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    similarity_score = serializers.FloatField()
    liveness_score = serializers.FloatField()
    fraud_probability = serializers.FloatField()
    verified_badge = serializers.BooleanField()
    rejection_reasons = serializers.ListField(child=serializers.CharField(), required=False)
    session = UserVerificationSerializer(required=False)


class VerificationStartResponseSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    session_token = serializers.UUIDField()
    expires_at = serializers.DateTimeField()
    instructions = serializers.ListField(child=serializers.CharField())
    liveness_steps = serializers.ListField(child=serializers.CharField())


class LivenessStepResponseSerializer(serializers.Serializer):
    step = serializers.CharField()
    passed = serializers.BooleanField()
    score = serializers.FloatField()
    detail = serializers.CharField()
    liveness_steps_completed = serializers.ListField(child=serializers.CharField())
