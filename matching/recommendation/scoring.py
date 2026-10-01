from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta

from django.utils import timezone

from accounts.geo import CITY_COORDS, find_city_center, haversine_km, profile_coordinates
from accounts.models import Profile
from duo_project.cache.presence import is_online

from matching.recommendation.types import SearchConfig


# Keyword groups for the occupation chips on /preferences (mirrors the
# frontend OCCUPATION_PREF_OPTIONS). Profile occupations are free text.
OCCUPATION_KEYWORDS = {
    "software": ['software', 'developer', 'programmer', 'it ', 'it,', 'web', 'data', 'devops', 'qa', 'tech'],
    "engineer": ['engineer'],
    "doctor": ['doctor', 'mbbs', 'physician', 'surgeon', 'dentist', 'md'],
    "health": ['nurse', 'pharmac', 'health', 'medical', 'lab tech', 'physio'],
    "teacher": ['teacher', 'professor', 'lecturer', 'tutor', 'educator'],
    "business": ['business', 'entrepreneur', 'founder', 'owner', 'self employed'],
    "banking": ['bank', 'finance', 'financial', 'investment', 'insurance'],
    "accountant": ['accountant', 'accounting', 'auditor', 'chartered'],
    "government": ['government', 'civil servant', 'officer', 'ministry', 'nepal rastra'],
    "security": ['army', 'police', 'armed', 'military', 'security'],
    "lawyer": ['lawyer', 'advocate', 'legal', 'attorney', 'judge'],
    "creative": ['designer', 'design', 'artist', 'creative', 'photographer', 'musician'],
    "architect": ['architect'],
    "marketing": ['marketing', 'sales', 'brand', 'advertis'],
    "manager": ['manager', 'director', 'executive', 'ceo', 'head of', 'lead'],
    "consultant": ['consultant', 'advisor', 'analyst'],
    "aviation": ['pilot', 'aviation', 'cabin crew', 'air hostess', 'airline'],
    "hospitality": ['hotel', 'hospitality', 'tourism', 'tour', 'travel', 'chef'],
    "media": ['journalist', 'media', 'reporter', 'editor', 'writer', 'content'],
    "ngo": ['ngo', 'ingo', 'development', 'social worker', 'un '],
    "research": ['research', 'scientist', 'phd'],
    "abroad": ['abroad', 'foreign employment', 'overseas'],
    "student": ['student'],
}


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
    # Feet and inches, e.g. 5'6", 5 ft 6 in, 5'
    match = re.search(r"(\d)\s*(?:'|ft|feet)\s*(\d{1,2})?", value, flags=re.IGNORECASE)
    if match:
        inches = int(match.group(1)) * 12 + int(match.group(2) or 0)
        return round(inches * 2.54)
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


# How well two relationship goals fit together (Hinge / Bumble "dating intentions"
# style): same goal is best, neighbouring intents are fine, serious vs casual clash.
GOAL_COMPATIBILITY = {
    ("serious", "serious"): 1.0,
    ("dating", "dating"): 1.0,
    ("casual", "casual"): 1.0,
    ("serious", "dating"): 0.6,
    ("dating", "serious"): 0.6,
    ("dating", "casual"): 0.6,
    ("casual", "dating"): 0.6,
}


def _goal_fit(a: str, b: str) -> float:
    a, b = (a or "").strip(), (b or "").strip()
    if not a or not b:
        return 0.4  # unknown on one side: neutral-low
    return GOAL_COMPATIBILITY.get((a, b), 0.0)


def _relationship_match_score(goal: str | None, candidate_goal: str) -> float:
    """Goal chosen in the match filter (hard filter already applied)."""
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

    candidate_occupation = (candidate.occupation or "").strip().lower()
    occupation_groups = _pref_list(viewer_prefs, "preferredOccupations")
    if occupation_groups:
        # Pad so short keywords like "it " also match at the end of the text.
        padded = f" {candidate_occupation} "
        if any(
            keyword in padded
            for group in occupation_groups
            for keyword in OCCUPATION_KEYWORDS.get(group, [group])
        ):
            score += 5.0
    preferred_occupation = (viewer.pref_occupation or "").strip().lower()
    if not occupation_groups and preferred_occupation and candidate_occupation:
        if preferred_occupation in candidate_occupation or candidate_occupation in preferred_occupation:
            score += 5.0

    candidate_prefs = _parse_pref_values(candidate.pref_values)
    preferred_levels = _pref_list(viewer_prefs, "preferredEducationLevels")
    if preferred_levels:
        if (candidate_prefs.get("educationLevel") or "").strip().lower() in preferred_levels:
            score += 5.0
    else:
        preferred_education = (viewer_prefs.get("educationLevel") or viewer.education or "").strip().lower()
        candidate_education = (candidate.education or "").strip().lower()
        if preferred_education and candidate_education and preferred_education in candidate_education:
            score += 5.0

    score += _explicit_preference_score(viewer_prefs, candidate, candidate_prefs)

    # Height range from /preferences: pref_min_height and pref_values.preferredMaxHeight
    # (either side may be empty = no limit).
    min_height = _parse_height_cm(viewer.pref_min_height)
    max_height = _parse_height_cm(viewer_prefs.get("preferredMaxHeight", ""))
    candidate_height = _parse_height_cm(_parse_pref_values(candidate.pref_values).get("height", ""))
    if (min_height or max_height) and candidate_height:
        if (not min_height or candidate_height >= min_height) and (
            not max_height or candidate_height <= max_height
        ):
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

    return min(score, 20.0)


def _pref_list(prefs: dict, key: str) -> set[str]:
    value = prefs.get(key) or []
    if isinstance(value, str):
        value = [value]
    return {str(item).strip().lower() for item in value if str(item).strip()}


def _explicit_preference_score(viewer_prefs: dict, candidate: Profile, candidate_prefs: dict) -> float:
    """Boost for the choices on the /preferences page (empty choice = any)."""
    score = 0.0

    caste = (viewer_prefs.get("preferredCaste") or "").strip().lower()
    if caste and caste == (candidate_prefs.get("caste") or "").strip().lower():
        score += 4.0

    rashi = (viewer_prefs.get("preferredRashi") or "").strip().lower()
    if rashi and rashi == (candidate_prefs.get("horoscope") or "").strip().lower():
        score += 2.0

    single_value_checks = (
        ("preferredFieldsOfStudy", (candidate_prefs.get("fieldOfStudy") or ""), 3.0),
        ("preferredWorkPreferences", (candidate.work_preference or ""), 3.0),
        ("preferredIncomes", (candidate_prefs.get("monthlyIncome") or ""), 2.0),
    )
    for key, candidate_value, points in single_value_checks:
        wanted = _pref_list(viewer_prefs, key)
        if wanted and candidate_value.strip().lower() in wanted:
            score += points

    tags = {str(tag).strip().lower() for tag in (candidate.lifestyle_tags or [])}
    for key, prefix, points in (
        ("preferredPersonalities", "", 2.0),
        ("preferredLifestyles", "", 2.0),
        ("preferredExercise", "exercise:", 2.0),
    ):
        wanted = _pref_list(viewer_prefs, key)
        if wanted and any(f"{prefix}{value}" in tags for value in wanted):
            score += points
    for key, prefix in (("preferredSmoking", "smoking:"), ("preferredDrinking", "drinking:")):
        wanted = _pref_list(viewer_prefs, key)
        if wanted and any(f"{prefix}{value}" in tags for value in wanted):
            score += 2.0

    languages = _pref_list(viewer_prefs, "preferredLanguages")
    if languages:
        spoken = {str(lang).strip().lower() for lang in (candidate_prefs.get("languages") or [])}
        if languages & spoken:
            score += 3.0

    interests = _pref_list(viewer_prefs, "preferredInterests")
    if interests:
        score += min(6.0, len(interests & tags) * 2.0)

    return score


PROFILE_COMPAT_CAP = 30.0


def _gender_code_for_pref(pref_gender: str) -> set[str] | None:
    return {"women": {"F"}, "men": {"M"}}.get((pref_gender or "everyone").strip())


def is_mutual_gender_interest(viewer: Profile, candidate: Profile) -> bool:
    """Reciprocal match rule used by major dating apps: the candidate must also be
    open to the viewer's gender. Unknown gender or "everyone" always passes."""
    wanted = _gender_code_for_pref(candidate.pref_gender)
    viewer_gender = (viewer.gender or "").strip()
    if not wanted or not viewer_gender:
        return True
    return viewer_gender in wanted


def _profile_compatibility_score(
    viewer: Profile, candidate: Profile, *, goal_filter_set: bool
) -> float:
    """Compatibility from the viewer's own registration / profile data.

    This is the first-priority soft layer: relationship intent (when no goal
    filter is set), two-way age fit, shared languages and interests, religion
    stance and smoking habits.
    """
    score = 0.0
    viewer_prefs = _parse_pref_values(viewer.pref_values)
    candidate_prefs = _parse_pref_values(candidate.pref_values)

    # Relationship intent from registration, used when the filter says "any goal".
    if not goal_filter_set:
        score += 12.0 * _goal_fit(viewer.relationship_goal, candidate.relationship_goal)

    # Two-way age fit: is the viewer inside the candidate's own age range?
    viewer_age = viewer.age or 0
    if viewer_age and candidate.pref_age_min and candidate.pref_age_max:
        if candidate.pref_age_min <= viewer_age <= candidate.pref_age_max:
            score += 5.0
        elif candidate.pref_age_min - 3 <= viewer_age <= candidate.pref_age_max + 3:
            score += 2.0

    # Shared languages (people who can talk comfortably).
    own_langs = {str(l).strip().lower() for l in (viewer_prefs.get("languages") or [])}
    their_langs = {str(l).strip().lower() for l in (candidate_prefs.get("languages") or [])}
    if own_langs and their_langs:
        score += min(6.0, len(own_langs & their_langs) * 3.0)

    # Religion stance from registration (matrimonial "inter-religion" answer).
    if viewer.religion and candidate.religion:
        same_religion = viewer.religion.strip().lower() == candidate.religion.strip().lower()
        if same_religion:
            score += 6.0 if (viewer_prefs.get("interReligion") or "").lower() == "no" else 2.0
        elif (viewer_prefs.get("interReligion") or "").lower() == "no":
            score -= 6.0

    # Habits: a non-smoker is unlikely to want a regular smoker.
    own_tags = {str(t).lower() for t in (viewer.lifestyle_tags or [])}
    their_tags = {str(t).lower() for t in (candidate.lifestyle_tags or [])}
    if "smoking:no" in own_tags and "smoking:yes" in their_tags:
        score -= 4.0

    # Shared interests.
    shared = {
        t for t in own_tags & their_tags
        if ":" not in t and t not in {"introvert", "ambivert", "extrovert", "active", "balanced", "relaxed"}
    }
    score += min(8.0, len(shared) * 2.0)

    return max(-10.0, min(score, PROFILE_COMPAT_CAP))


def viewer_has_explicit_preferences(viewer: Profile) -> bool:
    """True when the viewer set anything on /preferences (soft partner prefs)."""
    prefs = _parse_pref_values(viewer.pref_values)
    keys = (
        "preferredReligion", "preferredCaste", "preferredRashi", "preferredEducationLevels",
        "preferredFieldsOfStudy", "preferredWorkPreferences", "preferredIncomes",
        "preferredPersonalities", "preferredLifestyles", "preferredSmoking", "preferredDrinking",
        "preferredExercise", "preferredInterests", "preferredLanguages", "preferredOccupations",
        "preferredMaxHeight",
    )
    return bool(viewer.pref_min_height and _parse_height_cm(viewer.pref_min_height)) or any(
        prefs.get(key) not in (None, "", []) for key in keys
    )


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


def _known_city(text: str) -> str | None:
    lowered = (text or "").lower()
    return next((city for city in CITY_COORDS if city in lowered), None)


def viewer_anchor(profile: Profile) -> tuple[str, tuple[float, float]]:
    """Point that discovery distance is measured from.

    A search city (pref_location) that differs from the viewer's own city wins,
    so "show me people in Pokhara" works from Kathmandu. Otherwise the viewer's
    own position is used, preferring live GPS.
    """
    own_location = (profile.location or "").strip()
    search_location = (profile.pref_location or "").strip()
    search_city = _known_city(search_location)
    if search_city and search_city != _known_city(own_location):
        return search_location, find_city_center(search_city)

    location = own_location or search_location or "Kathmandu, Nepal"
    return location, profile_coordinates(location, profile.user_id, profile.pref_values)


def candidate_distance_km(viewer_coords: tuple[float, float], candidate: Profile) -> float:
    coords = profile_coordinates(candidate.location, candidate.user_id, candidate.pref_values)
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

    if not config.ignore_distance and distance_km > config.max_distance_km:
        return False

    if config.apply_location and config.location_pref:
        if _location_match_score(config.location_pref, candidate.location or "") <= 0:
            return False

    if config.gender == "women" and candidate.gender != "F":
        return False
    if config.gender == "men" and candidate.gender != "M":
        return False

    if not is_mutual_gender_interest(viewer, candidate):
        return False

    if config.verified_only and not candidate.is_verified:
        return False

    if config.relationship_goal and config.relationship_goal != "everyone":
        # A different goal is excluded; an unset goal passes but scores lower.
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
    goal_filter_set = bool(config.relationship_goal and config.relationship_goal != "everyone")
    score += _profile_compatibility_score(viewer, candidate, goal_filter_set=goal_filter_set)
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

    # With no /preferences set, show a varied ("random") mix within the goal-ordered
    # ranking, like other apps' default feeds; otherwise keep ordering stable.
    jitter_weight = 1.0 if viewer_has_explicit_preferences(viewer) else 4.0
    score += _diversity_jitter(viewer.user_id, candidate.id) * jitter_weight
    return round(score, 3)
