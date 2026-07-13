from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta

from django.utils import timezone

from accounts.geo import CITY_COORDS, haversine_km, profile_coordinates
from accounts.models import Profile
from duo_project.cache.presence import is_online

from matching.recommendation.types import SearchConfig


def _parse_pref_values(raw: str) -> dict:
    if not (raw or "").strip():
        return {}
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}


def _parse_height_cm(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(\d+)\s*cm", value, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _location_match_score(location_pref: str, candidate_location: str) -> float:
    pref = (location_pref or "").strip().lower()
    location = (candidate_location or "").strip().lower()
    if not pref or not location:
        return 0.0
    if pref in location or location in pref:
        return 30.0
    if any(city in location for city in CITY_COORDS if city in pref):
        return 30.0
    city_part = pref.split(",")[0].strip()
    if city_part and city_part in location:
        return 22.0
    return 0.0


def _age_match_score(age_min: int, age_max: int, candidate_age: int | None) -> float:
    age = candidate_age or 0
    if not age:
        return 0.0
    if age_min <= age <= age_max:
        center = (age_min + age_max) / 2
        distance_from_center = abs(age - center)
        span = max(1, age_max - age_min)
        return max(12.0, 25.0 - (distance_from_center / span) * 10.0)
    if age_min - 2 <= age <= age_max + 2:
        return 8.0
    if age_min - 5 <= age <= age_max + 5:
        return 4.0
    return 0.0


def _distance_match_score(distance_km: float, max_km: int) -> float:
    if distance_km <= max_km:
        ratio = min(1.0, distance_km / max(1, max_km))
        return max(4.0, 20.0 - ratio * 16.0)
    overflow = distance_km - max_km
    return max(0.0, 6.0 - overflow * 0.15)


def _relationship_match_score(goal: str | None, candidate_goal: str) -> float:
    if not goal or goal == "everyone":
        return 6.0
    if candidate_goal == goal:
        return 10.0
    if not candidate_goal:
        return 3.0
    return 0.0


def _gender_match_score(pref_gender: str, candidate_gender: str) -> float:
    if pref_gender == "everyone":
        return 5.0
    if pref_gender == "women" and candidate_gender == "F":
        return 8.0
    if pref_gender == "men" and candidate_gender == "M":
        return 8.0
    return 0.0


def _soft_preference_score(viewer: Profile, candidate: Profile) -> float:
    score = 0.0
    viewer_prefs = _parse_pref_values(viewer.pref_values)

    preferred_religion = (viewer_prefs.get("preferredReligion") or "").strip()
    if preferred_religion and candidate.religion and preferred_religion.lower() == candidate.religion.lower():
        score += 10.0

    preferred_occupation = (viewer.pref_occupation or "").strip().lower()
    candidate_occupation = (candidate.occupation or "").strip().lower()
    if preferred_occupation and candidate_occupation:
        if preferred_occupation in candidate_occupation or candidate_occupation in preferred_occupation:
            score += 5.0

    preferred_education = (viewer_prefs.get("educationLevel") or viewer.education or "").strip().lower()
    candidate_education = (candidate.education or "").strip().lower()
    if preferred_education and candidate_education and preferred_education in candidate_education:
        score += 5.0

    preferred_height = _parse_height_cm(viewer.pref_min_height)
    candidate_height = _parse_height_cm(_parse_pref_values(candidate.pref_values).get("height", ""))
    if preferred_height and candidate_height and candidate_height >= preferred_height:
        score += 4.0

    viewer_tags = {str(tag).lower() for tag in (viewer.lifestyle_tags or [])}
    candidate_tags = {str(tag).lower() for tag in (candidate.lifestyle_tags or [])}
    overlap = viewer_tags & candidate_tags
    if overlap:
        score += min(6.0, len(overlap) * 2.0)

    for key in ("interCaste", "interReligion"):
        pref_value = (viewer_prefs.get(key) or "").strip().lower()
        if pref_value in {"yes", "open", "preferred"}:
            score += 2.0

    return min(score, 25.0)


def _activity_boost(candidate: Profile) -> float:
    if is_online(candidate.user_id):
        return 15.0

    now = timezone.now()
    last_login = getattr(candidate.user, "last_login", None)
    updated_at = candidate.updated_at

    reference = last_login or updated_at
    if not reference:
        return 0.0

    if reference >= now - timedelta(days=1):
        return 12.0
    if reference >= now - timedelta(days=7):
        return 8.0
    if reference >= now - timedelta(days=30):
        return 4.0
    return 0.0


def _popularity_boost(candidate: Profile) -> float:
    likes = int(getattr(candidate, "likes_received_count", 0) or 0)
    matches = int(getattr(candidate, "matches_as_user1_count", 0) or 0) + int(
        getattr(candidate, "matches_as_user2_count", 0) or 0
    )
    completeness = int(candidate.profile_completeness or 0)

    score = min(8.0, likes * 0.4)
    score += min(8.0, matches * 1.5)
    score += completeness * 0.08
    if candidate.photo_url or (candidate.photo_urls or []):
        score += 4.0
    if (candidate.bio or "").strip():
        score += 2.0
    if candidate.is_verified:
        score += 3.0
    return min(score, 20.0)


def _diversity_jitter(viewer_id: int, profile_id: int) -> float:
    digest = hashlib.md5(f"{viewer_id}:{profile_id}:{date.today().isoformat()}".encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF * 3.0


def viewer_anchor(profile: Profile) -> tuple[str, tuple[float, float]]:
    location = (profile.pref_location or profile.location or "").strip() or "Kathmandu, Nepal"
    return location, profile_coordinates(location, profile.user_id)


def candidate_distance_km(viewer_coords: tuple[float, float], candidate: Profile) -> float:
    coords = profile_coordinates(candidate.location, candidate.user_id)
    return haversine_km(viewer_coords, coords)


def passes_hard_filters(
    viewer: Profile,
    candidate: Profile,
    config: SearchConfig,
    *,
    distance_km: float,
) -> bool:
    age = candidate.age or 0
    if age and (age < config.age_min or age > config.age_max):
        return False

    if distance_km > config.max_distance_km:
        return False

    if config.apply_location and config.location_pref:
        if _location_match_score(config.location_pref, candidate.location or "") <= 0:
            return False

    if config.gender == "women" and candidate.gender != "F":
        return False
    if config.gender == "men" and candidate.gender != "M":
        return False

    if config.verified_only and not candidate.is_verified:
        return False

    if config.relationship_goal and config.relationship_goal != "everyone":
        goal = (candidate.relationship_goal or "").strip()
        if goal and goal != config.relationship_goal:
            return False

    return True


def compute_recommendation_score(
    viewer: Profile,
    candidate: Profile,
    *,
    distance_km: float,
    config: SearchConfig,
) -> float:
    score = 0.0
    score += _location_match_score(config.location_pref or viewer.pref_location, candidate.location or "")
    score += _age_match_score(config.age_min, config.age_max, candidate.age)
    score += _distance_match_score(distance_km, config.max_distance_km)
    score += 10.0 if candidate.is_verified else 0.0
    score += _relationship_match_score(config.relationship_goal, candidate.relationship_goal or "")
    score += _gender_match_score(config.gender, candidate.gender or "")
    score += _soft_preference_score(viewer, candidate)
    score += _activity_boost(candidate)
    score += _popularity_boost(candidate)

    if config.prefer_verified and candidate.is_verified:
        score += 6.0
    if config.prefer_active:
        score += _activity_boost(candidate) * 0.5
    if config.prefer_popular:
        score += _popularity_boost(candidate) * 0.5
    if config.prefer_new:
        created = candidate.created_at
        if created and created >= timezone.now() - timedelta(days=14):
            score += 6.0

    score += _diversity_jitter(viewer.user_id, candidate.id)
    return round(score, 3)
