from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ActivityGridQuerySerializer
from .services.zones import compute_activity_zones, filter_zones_for_flags
from .throttles import ActivityRateThrottle


class ActivityZonesView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ActivityRateThrottle]

    @extend_schema(tags=["Activity"])
    def get(self, request):
        ser = ActivityGridQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        zones = compute_activity_zones(
            lat_min=data["lat_min"],
            lat_max=data["lat_max"],
            lon_min=data["lon_min"],
            lon_max=data["lon_max"],
            zoom=data.get("zoom", 4.0),
            step=data.get("step"),
            user=request.user,
        )

        flags = request.query_params
        if flags.get("trending") == "1":
            zones = filter_zones_for_flags(zones, trending_only=True)
        if flags.get("events") == "1":
            zones = filter_zones_for_flags(zones, events_only=True)
        if flags.get("friends") == "1":
            zones = filter_zones_for_flags(zones, friends_only=True)
        if flags.get("nearby") == "1":
            lat = flags.get("user_lat")
            lng = flags.get("user_lng")
            if lat and lng:
                zones = filter_zones_for_flags(
                    zones,
                    nearby_km=float(flags.get("nearby_km", 120)),
                    user_lat=float(lat),
                    user_lng=float(lng),
                )

        return Response(
            {
                "zones": zones,
                "updated_at": __import__("django.utils.timezone", fromlist=["timezone"]).timezone.now().isoformat(),
            }
        )
