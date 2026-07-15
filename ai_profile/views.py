from __future__ import annotations

import json

from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Profile
from ai_profile.serializers import (
    ProfileGenerateRequestSerializer,
    ProfileGenerateResponseSerializer,
)
from ai_profile.services.profile_generator import ProfileGenerator


class ProfileGenerateView(APIView):
    """Offline NLG endpoint: build bio / future goals / looking-for from profile fields."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["AI Profile"],
        request=ProfileGenerateRequestSerializer,
        responses={200: ProfileGenerateResponseSerializer},
        summary="Generate dating profile copy (offline, no LLM)",
    )
    def post(self, request):
        serializer = ProfileGenerateRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        profile, _ = Profile.objects.get_or_create(user=request.user)
        generator = ProfileGenerator(
            language=data.get("language", "en"),
            style=data.get("style", "friendly"),
        )
        result = generator.generate_for_profile(
            profile,
            force=bool(data.get("force")),
            persist=True,
        )

        if data.get("apply"):
            self._apply_to_profile(profile, result)

        payload = {
            "bio": result.bio,
            "future_goals": result.future_goals,
            "looking_for": result.looking_for,
            "traits": result.traits,
            "style": result.style,
            "language": result.language,
            "cached": result.cached,
        }
        return Response(payload, status=status.HTTP_200_OK)

    @staticmethod
    def _apply_to_profile(profile: Profile, result) -> None:
        profile.bio = result.bio
        prefs: dict = {}
        raw = profile.pref_values
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    prefs = parsed
            except (TypeError, ValueError, json.JSONDecodeError):
                prefs = {}
        elif isinstance(raw, dict):
            prefs = dict(raw)

        prefs["futureGoals"] = result.future_goals
        prefs["lookingForText"] = result.looking_for
        prefs["aiGeneratedTraits"] = result.traits
        profile.pref_values = json.dumps(prefs)
        profile.save(update_fields=["bio", "pref_values", "updated_at"])
