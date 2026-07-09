from rest_framework import serializers

from .defaults import merge_avatar_config
from .models import AvatarConfig, AvatarOutfit


class AvatarConfigSerializer(serializers.ModelSerializer):
    config = serializers.JSONField()

    class Meta:
        model = AvatarConfig
        fields = ("config", "version", "updated_at")
        read_only_fields = ("version", "updated_at")

    def validate_config(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("config must be an object")
        if len(str(value)) > 20_000:
            raise serializers.ValidationError("config too large")
        return merge_avatar_config(value)


class AvatarOutfitSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvatarOutfit
        fields = ("id", "name", "config", "is_favorite", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_config(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("config must be an object")
        return merge_avatar_config(value)

    def validate_name(self, value):
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("name is required")
        if len(name) > 80:
            raise serializers.ValidationError("name too long")
        return name
