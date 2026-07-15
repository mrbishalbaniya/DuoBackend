import json
import math
from datetime import timedelta
from typing import Any, Optional, Tuple

from django.utils import timezone

CITY_COORDS = {
    "kathmandu": (27.7172, 85.324),
    "pokhara": (28.2096, 83.9856),
    "lalitpur": (27.6588, 85.3247),
    "bhaktapur": (27.671, 85.4298),
    "chitwan": (27.5291, 84.3542),
    "biratnagar": (26.4525, 87.2718),
    "dharan": (26.8147, 87.2848),
    "butwal": (27.7, 83.4483),
}

DEFAULT_CENTER = (27.7172, 85.324)
LIVE_LOCATION_MAX_AGE = timedelta(minutes=15)


def is_live_location_fresh(updated_at) -> bool:
    if not updated_at:
        return False
    return timezone.now() - updated_at <= LIVE_LOCATION_MAX_AGE


def update_pref_values_gps(pref_values: Any, lat: float, lng: float) -> str:
    try:
        data = json.loads(pref_values) if isinstance(pref_values, str) else dict(pref_values or {})
    except (TypeError, ValueError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data["gps"] = {"lat": lat, "lng": lng}
    return json.dumps(data)


def resolve_map_coordinates(
    *,
    location: str | None,
    user_id: int | str | None,
    pref_values: Any = None,
    live_latitude: float | None = None,
    live_longitude: float | None = None,
    live_location_updated_at=None,
) -> Tuple[float, float]:
    if (
        live_latitude is not None
        and live_longitude is not None
        and is_live_location_fresh(live_location_updated_at)
        and abs(live_latitude) <= 90
        and abs(live_longitude) <= 180
    ):
        return live_latitude, live_longitude

    gps = gps_from_pref_values(pref_values)
    if gps is not None:
        return gps

    return profile_coordinates(location, user_id, pref_values)


def map_location_payload(profile) -> dict[str, Any]:
    lat, lng = resolve_map_coordinates(
        location=profile.location,
        user_id=getattr(profile, "user_id", None),
        pref_values=profile.pref_values,
        live_latitude=profile.live_latitude,
        live_longitude=profile.live_longitude,
        live_location_updated_at=profile.live_location_updated_at,
    )
    is_live = bool(
        profile.live_latitude is not None
        and profile.live_longitude is not None
        and is_live_location_fresh(profile.live_location_updated_at)
    )
    return {
        "map_latitude": lat,
        "map_longitude": lng,
        "location_is_live": is_live,
        "location_updated_at": (
            profile.live_location_updated_at.isoformat()
            if profile.live_location_updated_at
            else None
        ),
    }


def _hash_seed(value: str) -> int:
    h = 0
    for ch in value:
        h = ((h << 5) - h + ord(ch)) & 0xFFFFFFFF
    return abs(h)


def find_city_center(location: str) -> Tuple[float, float]:
    normalized = (location or "").lower()
    for city, coords in CITY_COORDS.items():
        if city in normalized:
            return coords
    return DEFAULT_CENTER


def gps_from_pref_values(pref_values: Any) -> Optional[Tuple[float, float]]:
    if not pref_values:
        return None
    try:
        data = json.loads(pref_values) if isinstance(pref_values, str) else pref_values
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    gps = data.get("gps")
    if not isinstance(gps, dict):
        return None
    try:
        lat = float(gps.get("lat", gps.get("latitude")))
        lng = float(gps.get("lng", gps.get("longitude")))
    except (TypeError, ValueError):
        return None
    if abs(lat) > 90 or abs(lng) > 180:
        return None
    return lat, lng


def profile_coordinates(
    location: str | None,
    user_id: int | str | None,
    pref_values: Any = None,
) -> Tuple[float, float]:
    gps = gps_from_pref_values(pref_values)
    if gps is not None:
        return gps

    base = find_city_center((location or "").strip() or "Kathmandu, Nepal")
    seed = _hash_seed(str(user_id if user_id is not None else location or "0"))
    angle = (seed % 360) * (math.pi / 180)
    radius = 0.008 + (seed % 100) / 10000
    return (
        base[0] + math.cos(angle) * radius,
        base[1] + math.sin(angle) * radius,
    )


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    x = (
        math.sin(d_lat / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(d_lon / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(x))
