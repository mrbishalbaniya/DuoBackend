from rest_framework import serializers

from update.models import AppVersion
from update.services.release_notes import parse_release_notes, resolve_release_title, sanitize_release_notes


class AppVersionPublicSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False, allow_null=True)
    latest_version = serializers.CharField()
    minimum_version = serializers.CharField()
    build_number = serializers.IntegerField()
    apk_url = serializers.URLField(allow_blank=True, required=False, default="")
    title = serializers.CharField(required=False, allow_blank=True, default="")
    release_title = serializers.CharField(required=False, allow_blank=True, default="")
    release_notes = serializers.ListField(child=serializers.CharField())
    force_update = serializers.BooleanField()
    soft_update = serializers.BooleanField()
    emergency_update = serializers.BooleanField()
    mandatory = serializers.BooleanField(required=False, default=False)
    file_size = serializers.CharField()
    size = serializers.CharField(required=False, allow_blank=True, default="")
    file_size_bytes = serializers.IntegerField()
    checksum_sha256 = serializers.CharField(allow_blank=True, required=False, default="")
    published_at = serializers.DateTimeField(allow_null=True, required=False)
    channel = serializers.CharField()
    platform = serializers.CharField()
    version = serializers.CharField(required=False, allow_blank=True, default="")
    build = serializers.IntegerField(required=False, default=0)
    update_available = serializers.BooleanField(required=False, default=False)
    update_blocked = serializers.BooleanField(required=False, default=False)
    download_count = serializers.IntegerField(required=False, default=0)


class AppVersionHistorySerializer(serializers.ModelSerializer):
    file_size = serializers.CharField(source="file_size_label", read_only=True)
    release_notes = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    release_title = serializers.SerializerMethodField()

    class Meta:
        model = AppVersion
        fields = [
            "id",
            "version",
            "build_number",
            "platform",
            "channel",
            "title",
            "release_title",
            "release_notes",
            "file_size",
            "checksum_sha256",
            "is_active",
            "is_published",
            "published_at",
            "download_count",
        ]

    def get_release_notes(self, obj):
        return sanitize_release_notes(obj.release_notes)

    def get_title(self, obj):
        return resolve_release_title(obj.release_title, version=obj.version)

    def get_release_title(self, obj):
        return self.get_title(obj)


class AppVersionPublishSerializer(serializers.Serializer):
    version = serializers.CharField(max_length=32)
    build_number = serializers.IntegerField(min_value=1)
    platform = serializers.ChoiceField(choices=AppVersion.PLATFORM_CHOICES, default=AppVersion.PLATFORM_ANDROID)
    channel = serializers.ChoiceField(choices=AppVersion.CHANNEL_CHOICES, default=AppVersion.CHANNEL_STABLE)
    apk_url = serializers.URLField(required=False, allow_blank=True)
    release_title = serializers.CharField(required=False, allow_blank=True, max_length=120)
    title = serializers.CharField(required=False, allow_blank=True, max_length=120)
    release_notes = serializers.JSONField(required=False)
    minimum_version = serializers.CharField(required=False, allow_blank=True, max_length=32)
    force_update = serializers.BooleanField(required=False, default=False)
    soft_update = serializers.BooleanField(required=False, default=True)
    emergency_update = serializers.BooleanField(required=False, default=False)
    activate = serializers.BooleanField(required=False, default=True)
    apk_file = serializers.FileField(required=False)

    def validate_release_notes(self, value):
        if isinstance(value, str):
            import json

            try:
                parsed = json.loads(value)
                return parse_release_notes(parsed)
            except json.JSONDecodeError:
                return parse_release_notes(value)
        return parse_release_notes(value)

    def validate(self, attrs):
        title = (attrs.get("release_title") or attrs.get("title") or "").strip()
        attrs["release_title"] = resolve_release_title(title) if title else ""
        return attrs
