from rest_framework import serializers

from .models import LoginHistory, SecurityEvent, TwoFactorMethod, UserDevice, UserSession


class PasswordVerifySerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)


class TwoFactorVerifySerializer(serializers.Serializer):
    code = serializers.CharField(max_length=16)


class TwoFactorSetupTotpResponseSerializer(serializers.Serializer):
    secret = serializers.CharField()
    otpauth_uri = serializers.CharField()


class TwoFactorEnableResponseSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    backup_codes = serializers.ListField(child=serializers.CharField())


class BackupCodesResponseSerializer(serializers.Serializer):
    codes = serializers.ListField(child=serializers.CharField())
    remaining = serializers.IntegerField()


class SecurityOverviewSerializer(serializers.Serializer):
    two_factor_enabled = serializers.BooleanField()
    two_factor_method = serializers.CharField(allow_null=True)
    biometric_enabled = serializers.BooleanField()
    active_devices = serializers.IntegerField()
    active_sessions = serializers.IntegerField()
    unread_alerts = serializers.IntegerField()
    remember_device_days = serializers.IntegerField()
    current_device_id = serializers.CharField()
    has_backup_codes = serializers.BooleanField()
    backup_codes_remaining = serializers.IntegerField(required=False, default=0)
    security_score = serializers.IntegerField(required=False, default=0)
    recommendations = serializers.ListField(required=False, default=list)
    email_verified = serializers.BooleanField(required=False, default=False)
    phone_verified = serializers.BooleanField(required=False, default=False)
    trusted_device_active = serializers.BooleanField(required=False, default=False)
    recent_suspicious = serializers.BooleanField(required=False, default=True)


class UserDeviceSerializer(serializers.ModelSerializer):
    is_current = serializers.SerializerMethodField()
    is_trusted_active = serializers.BooleanField(read_only=True)
    platform_label = serializers.CharField(source="get_platform_display", read_only=True)

    class Meta:
        model = UserDevice
        fields = [
            "id",
            "device_id",
            "device_name",
            "model",
            "platform",
            "platform_label",
            "os_version",
            "app_version",
            "browser",
            "ip_address",
            "location",
            "country",
            "city",
            "push_token",
            "is_trusted",
            "is_trusted_active",
            "is_current",
            "last_active",
            "login_time",
        ]

    def get_is_current(self, obj) -> bool:
        current_id = self.context.get("current_device_id", "")
        return bool(current_id and obj.device_id == current_id)


class UserSessionSerializer(serializers.ModelSerializer):
    device = UserDeviceSerializer(read_only=True)

    class Meta:
        model = UserSession
        fields = [
            "id",
            "device",
            "ip_address",
            "is_active",
            "created_at",
            "last_active",
        ]


class LoginHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginHistory
        fields = [
            "id",
            "success",
            "ip_address",
            "location",
            "country",
            "city",
            "device_name",
            "browser",
            "os_name",
            "failure_reason",
            "event_type",
            "is_current",
            "created_at",
        ]


class SecurityEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityEvent
        fields = [
            "id",
            "event_type",
            "title",
            "message",
            "metadata",
            "ip_address",
            "severity",
            "is_read",
            "created_at",
        ]


class DeviceRenameSerializer(serializers.Serializer):
    device_name = serializers.CharField(max_length=128)


class LogoutAllSerializer(serializers.Serializer):
    keep_current = serializers.BooleanField(default=True)
    device_id = serializers.CharField(required=False, allow_blank=True)
    refresh_token = serializers.CharField(required=False, allow_blank=True)


class BiometricEnableSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)
    device_id = serializers.CharField()
    device_name = serializers.CharField(required=False, allow_blank=True)
    model = serializers.CharField(required=False, allow_blank=True)
    platform = serializers.CharField(required=False, allow_blank=True)
    os_version = serializers.CharField(required=False, allow_blank=True)
    app_version = serializers.CharField(required=False, allow_blank=True)


class BiometricLoginSerializer(serializers.Serializer):
    token = serializers.CharField()
    device_id = serializers.CharField()


class BiometricStatusSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()


class TwoFactorLoginChallengeSerializer(serializers.Serializer):
    challenge_token = serializers.CharField()
    code = serializers.CharField(max_length=16)
    device_id = serializers.CharField(required=False, allow_blank=True)
    device_name = serializers.CharField(required=False, allow_blank=True)
    model = serializers.CharField(required=False, allow_blank=True)
    platform = serializers.CharField(required=False, allow_blank=True)
    os_version = serializers.CharField(required=False, allow_blank=True)
    app_version = serializers.CharField(required=False, allow_blank=True)


class LoginChallengeResponseSerializer(serializers.Serializer):
    requires_2fa = serializers.BooleanField()
    challenge_token = serializers.CharField()
    methods = serializers.ListField(child=serializers.CharField())


class TwoFactorMethodChoiceSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=TwoFactorMethod.choices)
