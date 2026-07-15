"""Live map location updates."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.geo import update_pref_values_gps
from duo_project.cache import api_cache, invalidate_profile_caches
from duo_project.cache import keys as cache_keys


class LiveLocationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = request.user.profile
        if profile.location_ghost_mode:
            return Response(
                {"detail": "Ghost mode is enabled. Disable it to share your location."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lat_raw = request.data.get("latitude", request.data.get("lat"))
        lng_raw = request.data.get("longitude", request.data.get("lng"))
        try:
            lat = float(lat_raw)
            lng = float(lng_raw)
        except (TypeError, ValueError):
            return Response(
                {"detail": "latitude and longitude are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if abs(lat) > 90 or abs(lng) > 180:
            return Response(
                {"detail": "Invalid coordinates."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone

        profile.live_latitude = lat
        profile.live_longitude = lng
        profile.live_location_updated_at = timezone.now()
        profile.pref_values = update_pref_values_gps(profile.pref_values, lat, lng)
        profile.save(
            update_fields=[
                "live_latitude",
                "live_longitude",
                "live_location_updated_at",
                "pref_values",
                "updated_at",
            ]
        )
        invalidate_profile_caches(profile.id, request.user.id, reason="live_location")
        api_cache.delete(cache_keys.profile(profile.id))

        return Response(
            {
                "map_latitude": lat,
                "map_longitude": lng,
                "location_is_live": True,
                "location_updated_at": profile.live_location_updated_at.isoformat(),
            }
        )
