"""Aggregate live social activity into globe heatmap zones."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Iterable

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from accounts.geo import find_city_center, haversine_km, profile_coordinates
from accounts.models import Profile
from chat.models import Message
from matching.models import Match, ProfileVisit, Swipe

ACTIVITY_LEVELS = ("low", "moderate", "high", "trending", "viral")
BADGE_TYPES = ("trending", "event", "popular", "recommended")


@dataclass
class CellBucket:
    lat: float = 0.0
    lng: float = 0.0
    score: float = 0.0
    active_users: set[int] = field(default_factory=set)
    friend_users: set[int] = field(default_factory=set)
    locations: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    messages: int = 0
    matches: int = 0
    likes: int = 0


def _step_for_zoom(zoom: float) -> float:
    if zoom < 3:
        return 8.0
    if zoom < 5:
        return 4.0
    if zoom < 7:
        return 2.0
    if zoom < 9:
        return 0.8
    if zoom < 11:
        return 0.35
    if zoom < 13:
        return 0.12
    return 0.05


def _cell_center(lat: float, lng: float, step: float) -> tuple[float, float]:
    return round(lat / step) * step, round(lng / step) * step


def _in_bbox(lat: float, lng: float, lat_min: float, lat_max: float, lon_min: float, lon_max: float) -> bool:
    return lat_min <= lat <= lat_max and lon_min <= lng <= lon_max


def _decay(hours: float) -> float:
    return max(0.08, 1.0 - hours / 36.0)


def _hours_ago(when) -> float:
    if not when:
        return 48.0
    delta = timezone.now() - when
    return max(0.0, delta.total_seconds() / 3600.0)


def _score_to_level(score: float) -> str:
    if score >= 88:
        return "viral"
    if score >= 72:
        return "trending"
    if score >= 48:
        return "high"
    if score >= 22:
        return "moderate"
    return "low"


def _zone_name(locations: list[str], lat: float, lng: float) -> str:
    if locations:
        # Most common city fragment in bucket
        counts: dict[str, int] = defaultdict(int)
        for loc in locations:
            city = (loc or "").split(",")[0].strip()
            if city:
                counts[city] += 1
        if counts:
            return max(counts, key=counts.get)
    # Fallback: nearest known city
    best = "Activity Zone"
    best_dist = 1e9
    from accounts.geo import CITY_COORDS

    for city, (clat, clng) in CITY_COORDS.items():
        d = haversine_km((lat, lng), (clat, clng))
        if d < best_dist:
            best_dist = d
            best = city.title()
    return best


def _badges_for_bucket(bucket: CellBucket, level: str) -> list[str]:
    badges: list[str] = []
    if level in ("trending", "viral"):
        badges.append("trending")
    if bucket.matches >= 2 or level == "viral":
        badges.append("popular")
    if bucket.events:
        badges.append("event")
    if 22 <= bucket.score < 72 and bucket.active_users and len(bucket.active_users) >= 3:
        badges.append("recommended")
    return badges


def _friend_ids(user: User | None) -> set[int]:
    if not user or not user.is_authenticated:
        return set()
    ids: set[int] = set()
    matches = Match.objects.filter(Q(user1=user) | Q(user2=user)).only("user1_id", "user2_id")
    for m in matches:
        ids.add(m.user2_id if m.user1_id == user.id else m.user1_id)
    return ids


def _add_to_cell(
    cells: dict[tuple[float, float], CellBucket],
    lat: float,
    lng: float,
    step: float,
    weight: float,
    user_id: int | None,
    friend_ids: set[int],
    location: str | None = None,
):
    key = _cell_center(lat, lng, step)
    bucket = cells.get(key)
    if not bucket:
        bucket = CellBucket(lat=key[0], lng=key[1])
        cells[key] = bucket
    bucket.score += weight
    if user_id:
        bucket.active_users.add(user_id)
        if user_id in friend_ids:
            bucket.friend_users.add(user_id)
    if location:
        bucket.locations.append(location)


def compute_activity_zones(
    *,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    zoom: float = 4.0,
    step: float | None = None,
    user: User | None = None,
    min_level: str | None = None,
) -> list[dict]:
    step = step or _step_for_zoom(zoom)
    friend_ids = _friend_ids(user)
    cells: dict[tuple[float, float], CellBucket] = {}
    since = timezone.now() - timedelta(hours=36)

    # Base density from registered profiles (privacy-safe aggregate)
    for profile in Profile.objects.select_related("user").only("location", "user_id").iterator():
        lat, lng = profile_coordinates(profile.location, profile.user_id, profile.pref_values)
        if not _in_bbox(lat, lng, lat_min, lat_max, lon_min, lon_max):
            continue
        _add_to_cell(
            cells,
            lat,
            lng,
            step,
            weight=1.8,
            user_id=profile.user_id,
            friend_ids=friend_ids,
            location=profile.location,
        )

    # Recent profile visits
    for visit in (
        ProfileVisit.objects.filter(last_visited_at__gte=since)
        .select_related("viewed_user__profile")
        .iterator()
    ):
        try:
            profile = visit.viewed_user.profile
        except Profile.DoesNotExist:
            continue
        lat, lng = profile_coordinates(profile.location, profile.user_id, profile.pref_values)
        if not _in_bbox(lat, lng, lat_min, lat_max, lon_min, lon_max):
            continue
        w = 2.4 * _decay(_hours_ago(visit.last_visited_at))
        bucket_key = _cell_center(lat, lng, step)
        _add_to_cell(cells, lat, lng, step, w, visit.viewed_user_id, friend_ids, profile.location)
        cells[bucket_key].score += w * 0.2

    # Swipes & super likes
    for swipe in Swipe.objects.filter(created_at__gte=since).select_related("from_user__profile").iterator():
        try:
            profile = swipe.from_user.profile
        except Profile.DoesNotExist:
            continue
        lat, lng = profile_coordinates(profile.location, profile.user_id, profile.pref_values)
        if not _in_bbox(lat, lng, lat_min, lat_max, lon_min, lon_max):
            continue
        action_w = {"LIKE": 2.8, "SUPERLIKE": 5.5, "SKIP": 0.6}.get(swipe.action, 1.0)
        w = action_w * _decay(_hours_ago(swipe.created_at))
        key = _cell_center(lat, lng, step)
        _add_to_cell(cells, lat, lng, step, w, swipe.from_user_id, friend_ids, profile.location)
        if swipe.action in ("LIKE", "SUPERLIKE"):
            cells[key].likes += 1

    # New matches
    for match in (
        Match.objects.filter(matched_at__gte=since)
        .select_related("user1__profile", "user2__profile")
        .iterator()
    ):
        for u in (match.user1, match.user2):
            try:
                profile = u.profile
            except Profile.DoesNotExist:
                continue
            lat, lng = profile_coordinates(profile.location, profile.user_id, profile.pref_values)
            if not _in_bbox(lat, lng, lat_min, lat_max, lon_min, lon_max):
                continue
            w = 6.0 * _decay(_hours_ago(match.matched_at))
            key = _cell_center(lat, lng, step)
            _add_to_cell(cells, lat, lng, step, w, profile.user_id, friend_ids, profile.location)
            cells[key].matches += 1
            if match.compatibility_score >= 85:
                cells[key].events.append(f"High compatibility match ({match.compatibility_score}%)")

    # Chat messages
    for msg in (
        Message.objects.filter(timestamp__gte=since, is_deleted_for_everyone=False)
        .select_related("sender__profile")
        .iterator()
    ):
        try:
            profile = msg.sender.profile
        except Profile.DoesNotExist:
            continue
        lat, lng = profile_coordinates(profile.location, profile.user_id, profile.pref_values)
        if not _in_bbox(lat, lng, lat_min, lat_max, lon_min, lon_max):
            continue
        w = 1.6 * _decay(_hours_ago(msg.timestamp))
        key = _cell_center(lat, lng, step)
        _add_to_cell(cells, lat, lng, step, w, msg.sender_id, friend_ids, profile.location)
        cells[key].messages += 1

    # Synthetic live events for high-activity cells
    for key, bucket in cells.items():
        if bucket.score >= 55 and not bucket.events:
            name = _zone_name(bucket.locations, bucket.lat, bucket.lng)
            bucket.events.append(f"Live social hour in {name}")

    zones: list[dict] = []
    min_score = {"low": 0, "moderate": 22, "high": 48, "trending": 72, "viral": 88}.get(min_level or "low", 0)

    for key, bucket in cells.items():
        if not _in_bbox(bucket.lat, bucket.lng, lat_min, lat_max, lon_min, lon_max):
            continue

        # Zoom-based visibility: global view hides minor zones
        if zoom < 4 and bucket.score < 35:
            continue
        if zoom < 6 and bucket.score < 18:
            continue
        if zoom < 8 and bucket.score < 10:
            continue

        level = _score_to_level(bucket.score)
        if bucket.score < min_score:
            continue

        active = len(bucket.active_users)
        radius_km = _radius_for_level(level, zoom, active)
        badges = _badges_for_bucket(bucket, level)
        zone_name = _zone_name(bucket.locations, bucket.lat, bucket.lng)

        zones.append(
            {
                "id": f"zone-{key[0]:.3f}-{key[1]:.3f}",
                "lat": bucket.lat,
                "lng": bucket.lng,
                "score": round(min(100.0, bucket.score), 1),
                "level": level,
                "active_users": active,
                "friends_active": len(bucket.friend_users),
                "radius_km": round(radius_km, 2),
                "name": zone_name,
                "badges": badges,
                "events": bucket.events[:4],
                "messages": bucket.messages,
                "matches": bucket.matches,
                "likes": bucket.likes,
                "trending": level in ("trending", "viral"),
            }
        )

    zones.sort(key=lambda z: z["score"], reverse=True)
    max_zones = _max_zones_for_zoom(zoom)
    return zones[:max_zones]


def _radius_for_level(level: str, zoom: float, active_users: int) -> float:
    base = {
        "low": 28,
        "moderate": 45,
        "high": 70,
        "trending": 110,
        "viral": 160,
    }[level]
    zoom_scale = 1.0 if zoom < 5 else max(0.25, 1.4 - zoom * 0.1)
    user_boost = min(40.0, active_users * 2.5)
    return (base + user_boost) * zoom_scale


def _max_zones_for_zoom(zoom: float) -> int:
    if zoom < 4:
        return 18
    if zoom < 7:
        return 32
    if zoom < 10:
        return 48
    return 64


def filter_zones_for_flags(
    zones: Iterable[dict],
    *,
    trending_only: bool = False,
    events_only: bool = False,
    friends_only: bool = False,
    nearby_km: float | None = None,
    user_lat: float | None = None,
    user_lng: float | None = None,
) -> list[dict]:
    result: list[dict] = []
    for zone in zones:
        if trending_only and zone["level"] not in ("trending", "viral"):
            continue
        if events_only and "event" not in zone.get("badges", []):
            continue
        if friends_only and zone.get("friends_active", 0) < 1:
            continue
        if nearby_km is not None and user_lat is not None and user_lng is not None:
            d = haversine_km((user_lat, user_lng), (zone["lat"], zone["lng"]))
            if d > nearby_km:
                continue
        result.append(zone)
    return result
