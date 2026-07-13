from __future__ import annotations

from accounts.models import Profile

from matching.recommendation.types import SearchConfig


def build_search_stages(viewer: Profile) -> list[tuple[str, SearchConfig]]:
    """Progressive relaxation stages — never return empty while users exist."""
    age_min = int(viewer.pref_age_min or 22)
    age_max = int(viewer.pref_age_max or 35)
    distance = max(5, int(viewer.pref_max_distance_km or 50))
    location_pref = (viewer.pref_location or viewer.location or "").strip()
    gender = (viewer.pref_gender or "everyone").strip() or "everyone"
    relationship_goal = (viewer.pref_relationship_goal or "everyone").strip() or "everyone"
    verified_only = bool(viewer.pref_verified_only)

    base = dict(
        location_pref=location_pref,
        gender=gender,
        relationship_goal=relationship_goal,
        verified_only=verified_only,
    )

    return [
        (
            "strict",
            SearchConfig(
                age_min=age_min,
                age_max=age_max,
                max_distance_km=distance,
                apply_location=bool(location_pref),
                **base,
            ),
        ),
        (
            "distance_expanded",
            SearchConfig(
                age_min=age_min,
                age_max=age_max,
                max_distance_km=min(500, distance * 2),
                apply_location=bool(location_pref),
                **base,
            ),
        ),
        (
            "age_expanded_2",
            SearchConfig(
                age_min=max(18, age_min - 2),
                age_max=min(80, age_max + 2),
                max_distance_km=min(500, distance * 2),
                apply_location=bool(location_pref),
                **base,
            ),
        ),
        (
            "age_expanded_5",
            SearchConfig(
                age_min=max(18, age_min - 5),
                age_max=min(80, age_max + 5),
                max_distance_km=min(500, distance * 3),
                apply_location=bool(location_pref),
                **base,
            ),
        ),
        (
            "ignore_relationship_goal",
            SearchConfig(
                age_min=max(18, age_min - 5),
                age_max=min(80, age_max + 5),
                max_distance_km=min(500, distance * 3),
                apply_location=bool(location_pref),
                location_pref=location_pref,
                gender=gender,
                relationship_goal=None,
                verified_only=verified_only,
            ),
        ),
        (
            "ignore_location",
            SearchConfig(
                age_min=max(18, age_min - 5),
                age_max=min(80, age_max + 5),
                max_distance_km=min(500, distance * 4),
                apply_location=False,
                location_pref=location_pref,
                gender=gender,
                relationship_goal=None,
                verified_only=verified_only,
            ),
        ),
        (
            "ignore_gender",
            SearchConfig(
                age_min=max(18, age_min - 5),
                age_max=min(80, age_max + 5),
                max_distance_km=min(500, distance * 5),
                apply_location=False,
                location_pref=location_pref,
                gender="everyone",
                relationship_goal=None,
                verified_only=verified_only,
            ),
        ),
        (
            "active_nearby",
            SearchConfig(
                age_min=max(18, age_min - 8),
                age_max=min(80, age_max + 8),
                max_distance_km=500,
                apply_location=False,
                location_pref=location_pref,
                gender="everyone",
                relationship_goal=None,
                verified_only=False,
                prefer_active=True,
            ),
        ),
        (
            "verified_users",
            SearchConfig(
                age_min=18,
                age_max=80,
                max_distance_km=500,
                apply_location=False,
                location_pref=location_pref,
                gender="everyone",
                relationship_goal=None,
                verified_only=False,
                prefer_verified=True,
            ),
        ),
        (
            "recently_active",
            SearchConfig(
                age_min=18,
                age_max=80,
                max_distance_km=500,
                apply_location=False,
                location_pref=location_pref,
                gender="everyone",
                relationship_goal=None,
                verified_only=False,
                prefer_active=True,
            ),
        ),
        (
            "popular_users",
            SearchConfig(
                age_min=18,
                age_max=80,
                max_distance_km=500,
                apply_location=False,
                location_pref=location_pref,
                gender="everyone",
                relationship_goal=None,
                verified_only=False,
                prefer_popular=True,
            ),
        ),
        (
            "new_users",
            SearchConfig(
                age_min=18,
                age_max=80,
                max_distance_km=500,
                apply_location=False,
                location_pref=location_pref,
                gender="everyone",
                relationship_goal=None,
                verified_only=False,
                prefer_new=True,
            ),
        ),
        (
            "all_available",
            SearchConfig(
                age_min=18,
                age_max=80,
                max_distance_km=500,
                apply_location=False,
                location_pref=location_pref,
                gender="everyone",
                relationship_goal=None,
                verified_only=False,
            ),
        ),
    ]
