from rest_framework import serializers
from .models import Swipe, Match
from accounts.serializers import LOCATION_PRIVACY_FIELDS, ProfileSerializer


class SwipeSerializer(serializers.Serializer):
    to_user_id = serializers.IntegerField()
    action = serializers.ChoiceField(choices=['LIKE', 'SKIP', 'SUPERLIKE'])


class MatchSerializer(serializers.ModelSerializer):
    other_user_profile = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = [
            'id', 'compatibility_score', 'matched_at', 'other_user_profile',
            'values_score', 'lifestyle_score', 'career_score', 'hobbies_score',
            'spark_factors', 'shared_interests', 'vision_insight', 'communication_insight',
        ]

    def get_other_user_profile(self, obj):
        request_user = self.context.get('request').user
        other_user = obj.get_other_user(request_user)
        profile = other_user.profile
        data = ProfileSerializer(profile, context=self.context).data
        for field in LOCATION_PRIVACY_FIELDS:
            data.pop(field, None)

        shared = profile.is_location_visible_to(request_user)
        data["location_shared"] = shared
        if not shared:
            data["location"] = ""
        return data


class LikedProfileSerializer(serializers.Serializer):
    swipe_id = serializers.IntegerField(source='id')
    profile = serializers.SerializerMethodField()
    liked_at = serializers.DateTimeField(source='created_at')
    action = serializers.CharField()
    locked = serializers.SerializerMethodField()

    def get_profile(self, obj):
        request_user = self.context.get('request').user
        other_user = obj.to_user if obj.from_user_id == request_user.id else obj.from_user
        return ProfileSerializer(other_user.profile).data

    def get_locked(self, obj):
        return bool(self.context.get('locked', False))


def mask_profile_for_paywall(profile_data: dict, *, swipe_id: int | None = None, visit_id: int | None = None) -> dict:
    seed = visit_id if visit_id is not None else swipe_id
    preview_distance_km = ((seed or 0) % 42) + 4
    return {
        "full_name": profile_data.get("full_name") or "Duo member",
        "photo_url": profile_data.get("photo_url"),
        "photo_urls": profile_data.get("photo_urls") or [],
        "age": profile_data.get("age"),
        "location": "",
        "preview_distance_km": preview_distance_km,
        "is_verified": False,
    }


class VisitedProfileSerializer(serializers.Serializer):
    visit_id = serializers.IntegerField(source="id")
    profile = serializers.SerializerMethodField()
    visited_at = serializers.DateTimeField(source="last_visited_at")
    locked = serializers.SerializerMethodField()

    def get_profile(self, obj):
        return ProfileSerializer(obj.viewer.profile).data

    def get_locked(self, obj):
        return bool(self.context.get("locked", False))
