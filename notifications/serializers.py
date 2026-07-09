from rest_framework import serializers

from notifications.models import DeviceToken


class DeviceTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512)
    platform = serializers.ChoiceField(
        choices=[choice[0] for choice in DeviceToken.PLATFORM_CHOICES],
        default=DeviceToken.PLATFORM_WEB,
    )
