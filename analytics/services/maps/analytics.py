"""Geographic and map analytics."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta

from django.utils import timezone

from accounts.geo import find_city_center, gps_from_pref_values
from accounts.models import Profile
from chat.models import Message
from matching.models import Match, ProfileVisit, Swipe


def get_map_analytics(filters: dict | None = None) -> dict:
    filters = filters or {}
    period = (filters.get("period") or "30d").strip()
    hours = {"7d": 24 * 7, "30d": 24 * 30, "90d": 24 * 90}.get(period, 24 * 30)
    since = timezone.now() - timedelta(hours=hours)

    locations = list(
        Profile.objects.exclude(location="")
        .exclude(location__isnull=True)
        .values_list("location", flat=True)[:8000]
    )
    counter = Counter(locations)
    top_locations = [{"location": loc, "count": cnt} for loc, cnt in counter.most_common(50)]

    zones = _build_city_heatmap_zones(since=since)

    return {
        "heatmap_zones": zones,
        "popular_locations": top_locations,
        "country_distribution": _aggregate_by_country(top_locations),
        "city_distribution": top_locations[:20],
        "total_with_location": len(locations),
        "period": period,
    }


def _city_key(location: str) -> str:
    text = (location or "").strip()
    if not text:
        return "Unknown"
    return text.split(",")[0].strip().title() or "Unknown"


def _coords_for_profile(profile: Profile) -> tuple[float, float, str]:
    """
    Map each profile to a city-center point for the heatmap.

    Prefer known city centers from `location` so labels stay accurate.
    Use stored GPS only when there is no usable city string.
    """
    location = (profile.location or "").strip()
    city = _city_key(location) if location else "Unknown"
    if city not in {"Unknown", "Nepal"} and location:
        lat, lng = find_city_center(location)
        return lat, lng, city

    gps = gps_from_pref_values(getattr(profile, "pref_values", None))
    if gps is not None:
        return gps[0], gps[1], city if city != "Unknown" else "GPS"

    lat, lng = find_city_center(location or "Kathmandu, Nepal")
    return lat, lng, city if city != "Unknown" else "Kathmandu"


def _zone_key(lat: float, lng: float) -> str:
    """Merge nearby labels (e.g. Kathmandu vs Kathmandu Metropolitan City)."""
    return f"{round(lat, 2)}_{round(lng, 2)}"


def _prefer_city_name(current: str, candidate: str) -> str:
    if not current or current in {"Nepal", "Unknown"}:
        return candidate
    if candidate in {"Nepal", "Unknown"}:
        return current
    # Prefer the more specific / longer local label.
    if len(candidate) > len(current) and current.lower() in candidate.lower():
        return candidate
    if len(current) > len(candidate) and candidate.lower() in current.lower():
        return current
    return current


def _build_city_heatmap_zones(*, since) -> list[dict]:
    """
    Aggregate activity onto accurate city coordinates.

    Avoids the globe-zoom cell grid (8°) that placed Kathmandu near 24N/88E.
    """
    buckets: dict[str, dict] = {}

    def bump(city: str, lat: float, lng: float, *, weight: float, user_id: int | None, kind: str):
        key = _zone_key(lat, lng)
        bucket = buckets.get(key)
        if not bucket:
            bucket = {
                "name": city,
                "lat": lat,
                "lng": lng,
                "score": 0.0,
                "users": set(),
                "likes": 0,
                "matches": 0,
                "messages": 0,
                "visits": 0,
                "profiles": 0,
            }
            buckets[key] = bucket
        else:
            bucket["name"] = _prefer_city_name(bucket["name"], city)
        bucket["score"] += weight
        if user_id:
            bucket["users"].add(user_id)
        if kind == "like":
            bucket["likes"] += 1
        elif kind == "match":
            bucket["matches"] += 1
        elif kind == "message":
            bucket["messages"] += 1
        elif kind == "visit":
            bucket["visits"] += 1
        elif kind == "profile":
            bucket["profiles"] += 1

    for profile in (
        Profile.objects.select_related("user")
        .only("location", "user_id", "pref_values")
        .iterator()
    ):
        lat, lng, city = _coords_for_profile(profile)
        bump(city, lat, lng, weight=1.5, user_id=profile.user_id, kind="profile")

    for visit in (
        ProfileVisit.objects.filter(last_visited_at__gte=since)
        .select_related("viewed_user__profile")
        .iterator()
    ):
        try:
            profile = visit.viewed_user.profile
        except Profile.DoesNotExist:
            continue
        lat, lng, city = _coords_for_profile(profile)
        bump(city, lat, lng, weight=2.2, user_id=visit.viewed_user_id, kind="visit")

    for swipe in (
        Swipe.objects.filter(created_at__gte=since)
        .select_related("from_user__profile")
        .iterator()
    ):
        try:
            profile = swipe.from_user.profile
        except Profile.DoesNotExist:
            continue
        lat, lng, city = _coords_for_profile(profile)
        weight = {"LIKE": 2.8, "SUPERLIKE": 5.0, "SKIP": 0.5}.get(swipe.action, 1.0)
        kind = "like" if swipe.action in ("LIKE", "SUPERLIKE") else "profile"
        bump(city, lat, lng, weight=weight, user_id=swipe.from_user_id, kind=kind)

    for match in (
        Match.objects.filter(matched_at__gte=since)
        .select_related("user1__profile", "user2__profile")
        .iterator()
    ):
        for user in (match.user1, match.user2):
            try:
                profile = user.profile
            except Profile.DoesNotExist:
                continue
            lat, lng, city = _coords_for_profile(profile)
            bump(city, lat, lng, weight=5.5, user_id=profile.user_id, kind="match")

    for msg in (
        Message.objects.filter(timestamp__gte=since, is_deleted_for_everyone=False)
        .select_related("sender__profile")
        .iterator()
    ):
        try:
            profile = msg.sender.profile
        except Profile.DoesNotExist:
            continue
        lat, lng, city = _coords_for_profile(profile)
        bump(city, lat, lng, weight=1.4, user_id=msg.sender_id, kind="message")

    if not buckets:
        return []

    max_score = max(b["score"] for b in buckets.values()) or 1.0
    zones: list[dict] = []
    for key, bucket in buckets.items():
        city = bucket["name"]
        clat, clng = float(bucket["lat"]), float(bucket["lng"])
        active = len(bucket["users"])
        score = round(min(100.0, (bucket["score"] / max_score) * 100.0), 1)
        if score >= 80:
            level = "viral"
        elif score >= 60:
            level = "trending"
        elif score >= 35:
            level = "high"
        elif score >= 15:
            level = "moderate"
        else:
            level = "low"

        # radius grows with active users but stays city-local
        radius_km = min(45.0, max(6.0, 5.0 + active * 0.55 + score * 0.12))
        slug = city.lower().replace(" ", "-")[:40]

        zones.append(
            {
                "id": f"city-{slug}-{key}",
                "lat": round(clat, 5),
                "lng": round(clng, 5),
                "score": score,
                "level": level,
                "active_users": active,
                "friends_active": 0,
                "radius_km": round(radius_km, 2),
                "name": city,
                "badges": ["popular"] if active >= 5 else [],
                "events": [],
                "messages": bucket["messages"],
                "matches": bucket["matches"],
                "likes": bucket["likes"],
                "profiles": bucket["profiles"],
                "visits": bucket["visits"],
                "trending": level in ("trending", "viral"),
            }
        )

    zones.sort(key=lambda z: (z["score"], z["active_users"]), reverse=True)
    return zones[:40]


def _aggregate_by_country(locations: list[dict]) -> list[dict]:
    countries: dict[str, int] = {}
    for item in locations:
        loc = item["location"]
        country = loc.split(",")[-1].strip() if "," in loc else loc
        countries[country] = countries.get(country, 0) + item["count"]
    return [{"country": k, "count": v} for k, v in sorted(countries.items(), key=lambda x: -x[1])]
