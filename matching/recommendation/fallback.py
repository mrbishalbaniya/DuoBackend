from __future__ import annotations

from accounts.models import Profile

from matching.recommendation.types import SearchConfig

AGE_FLOOR = 18
AGE_CEILING = 80
DISTANCE_CEILING_KM = 500


def build_search_stages(viewer: Profile) -> list[tuple[str, SearchConfig]]:
    """Discovery stages, strictest first.

    The viewer's explicit choices always hold in every stage: gender, relationship
    goal and verified-only. Distance and age are only widened when the viewer
    allows it (pref_expand_distance / pref_expand_age), mirroring the "show
    people further away / slightly out of range if I run out" switches.
    The typed location is the point distance is measured from, not a text match.
    """
    age_min = max(AGE_FLOOR, int(viewer.pref_age_min or 22))
    age_max = min(AGE_CEILING, int(viewer.pref_age_max or 35))
    if age_min > age_max:
        age_min, age_max = age_max, age_min
    distance = max(1, min(DISTANCE_CEILING_KM, int(viewer.pref_max_distance_km or 50)))
    location_pref = (viewer.pref_location or viewer.location or "").strip()
    gender = (viewer.pref_gender or "everyone").strip() or "everyone"
    relationship_goal = (viewer.pref_relationship_goal or "everyone").strip() or "everyone"
    verified_only = bool(viewer.pref_verified_only)
    expand_distance = bool(getattr(viewer, "pref_expand_distance", True))
    expand_age = bool(getattr(viewer, "pref_expand_age", True))

    def stage(name: str, *, age_pad: int = 0, distance_km: int = distance, anywhere: bool = False):
        return (
            name,
            SearchConfig(
                age_min=max(AGE_FLOOR, age_min - age_pad),
                age_max=min(AGE_CEILING, age_max + age_pad),
                max_distance_km=min(DISTANCE_CEILING_KM, distance_km),
                location_pref=location_pref,
                apply_location=False,
                gender=gender,
                relationship_goal=relationship_goal,
                verified_only=verified_only,
                ignore_distance=anywhere,
            ),
        )

    stages = [stage("strict")]

    if expand_distance:
        stages.append(stage("distance_expanded", distance_km=distance * 2))
        stages.append(stage("distance_expanded_more", distance_km=max(distance * 4, 100)))

    if expand_age:
        widest = max(distance * 4, 100) if expand_distance else distance
        stages.append(stage("age_expanded_2", age_pad=2, distance_km=widest))
        stages.append(stage("age_expanded_5", age_pad=5, distance_km=widest))

    if expand_distance:
        stages.append(stage("anywhere", age_pad=5 if expand_age else 0, anywhere=True))

    return stages


def stage_expansions(strict: SearchConfig, config: SearchConfig) -> list[str]:
    """Which limits a stage widened compared with the strict stage."""
    reasons = []
    if config.ignore_distance or config.max_distance_km > strict.max_distance_km:
        reasons.append("distance")
    if config.age_min < strict.age_min or config.age_max > strict.age_max:
        reasons.append("age")
    return reasons
