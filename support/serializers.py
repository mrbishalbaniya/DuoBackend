from rest_framework import serializers

from .models import SupportRequest, SupportRequestCategory


class SupportRequestCreateSerializer(serializers.ModelSerializer):
    category = serializers.ChoiceField(choices=SupportRequestCategory.choices)

    class Meta:
        model = SupportRequest
        fields = ["category", "subject", "message", "contact_email", "device_info"]

    def validate_message(self, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise serializers.ValidationError("Please provide a bit more detail.")
        return value
