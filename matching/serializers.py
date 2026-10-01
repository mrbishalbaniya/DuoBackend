from rest_framework import serializers
from .models import Swipe, Match
from accounts.serializers import LOCATION_PRIVACY_FIELDS, ProfileSerializer
from accounts.geo import map_location_payload


class SwipeSerializer(serializers.Serializer):
    to_user_id = serializers.IntegerField()
    action = serializers.ChoiceField(choices=['LIKE', 'SKIP', 'SUPERLIKE'])


class RewindSerializer(serializers.Serializer):
    to_user_id = serializers.IntegerField(required=False, min_value=1)


class UnlikeSerializer(serializers.Serializer):
    to_user_id = serializers.IntegerField()


class MatchSerializer(serializers.ModelSerializer):
    other_user_profile = serializers.SerializerMethodField()
    conversation_id = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = [
            'id', 'compatibility_score', 'matched_at', 'other_user_profile',
            'values_score', 'lifestyle_score', 'career_score', 'hobbies_score',
            'spark_factors', 'shared_interests', 'vision_insight', 'communication_insight',
            'conversation_id',
        ]

    def get_conversation_id(self, obj):
        convo = getattr(obj, "conversation", None)
        return getattr(convo, "public_id", None)

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
        else:
            data.update(map_location_payload(profile))
        return data


class LikedProfileSerializer(serializers.Serializer):
    swipe_id = serializers.IntegerField(source='id')
    profile = serializers.SerializerMethodField()
    liked_at = serializers.DateTimeField(source='created_at')
    action = serializers.CharField()
    locked = serializers.SerializerMethodField()
    # "matched" once both liked each other, else "pending"
    status = serializers.SerializerMethodField()
    conversation_id = serializers.SerializerMethodField()

    def _other_id(self, obj):
        request_user = self.context.get('request').user
        return obj.to_user_id if obj.from_user_id == request_user.id else obj.from_user_id

    def get_profile(self, obj):
        request_user = self.context.get('request').user
        other_user = obj.to_user if obj.from_user_id == request_user.id else obj.from_user
        return ProfileSerializer(other_user.profile, context=self.context).data

    def get_locked(self, obj):
        if self.get_status(obj) == "matched":
            return False  # a match is already revealed
        return bool(self.context.get('locked', False))

    def get_status(self, obj):
        return "matched" if self._other_id(obj) in (self.context.get("match_conversations") or {}) else "pending"

    def get_conversation_id(self, obj):
        return (self.context.get("match_conversations") or {}).get(self._other_id(obj))


def _blurred_photo(url):
    """Heavily blurred Cloudinary variant of a photo, or None if it can't be blurred."""
    if not url or "res.cloudinary.com" not in url or "/upload/" not in url:
        return None
    return url.replace("/upload/", "/upload/e_blur:2000,q_30,w_300/", 1)


def mask_profile_for_paywall(profile_data: dict, *, swipe_id: int | None = None, visit_id: int | None = None) -> dict:
    """Teaser for non-premium users: never send the real name or a clear photo.

    The client only blurs with CSS, so anything sent here is readable in the
    browser. Cloudinary photos are blurred server-side; other photos are dropped.
    """
    seed = visit_id if visit_id is not None else swipe_id
    preview_distance_km = ((seed or 0) % 42) + 4
    blurred = _blurred_photo(profile_data.get("photo_url"))
    return {
        "full_name": "Someone",
        "photo_url": blurred,
        "photo_urls": [blurred] if blurred else [],
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
        return ProfileSerializer(obj.viewer.profile, context=self.context).data

    def get_locked(self, obj):
        return bool(self.context.get("locked", False))
