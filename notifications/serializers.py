from rest_framework import serializers

from notifications.models import DeviceToken, NotificationPreference


class DeviceTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512)
    platform = serializers.ChoiceField(
        choices=[choice[0] for choice in DeviceToken.PLATFORM_CHOICES],
        default=DeviceToken.PLATFORM_WEB,
    )
    device_label = serializers.CharField(max_length=128, required=False, allow_blank=True)


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = (
            "push_enabled",
            "chat_enabled",
            "calls_enabled",
            "match_enabled",
            "likes_enabled",
            "marketing_enabled",
            "announcements_enabled",
            "verification_enabled",
            "payment_enabled",
            "sound_enabled",
            "vibration_enabled",
        )


class AdminBroadcastSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    body = serializers.CharField(max_length=2000)
    user_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )
    notification_type = serializers.CharField(max_length=64, default="admin_announcement")
    url = serializers.CharField(max_length=512, required=False, allow_blank=True, default="/")
