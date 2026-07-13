from __future__ import annotations

from django.db.models import QuerySet

from accounts.models import Profile

from matching.recommendation.fallback import build_search_stages
from matching.recommendation.queries import build_eligible_queryset
from matching.recommendation.scoring import (
    candidate_distance_km,
    compute_recommendation_score,
    passes_hard_filters,
    viewer_anchor,
)
from matching.recommendation.types import DiscoverResult, ScoredProfile, SearchConfig

RESULT_LIMIT = 25
CANDIDATE_POOL_MAX = 400
MIN_RESULTS_BEFORE_RELAX = 8


def _rank_candidates(
    viewer: Profile,
    queryset: QuerySet[Profile],
    config: SearchConfig,
) -> list[ScoredProfile]:
    _, viewer_coords = viewer_anchor(viewer)
    ranked: list[ScoredProfile] = []

    for candidate in queryset[:CANDIDATE_POOL_MAX]:
        distance = candidate_distance_km(viewer_coords, candidate)
        if not passes_hard_filters(viewer, candidate, config, distance_km=distance):
            continue
        score = compute_recommendation_score(
            viewer,
            candidate,
            distance_km=distance,
            config=config,
        )
        ranked.append(ScoredProfile(profile=candidate, score=score, distance_km=distance))

    ranked.sort(key=lambda row: (-row.score, row.distance_km, row.profile.id))
    return ranked


def discover_profiles(user) -> DiscoverResult:
    viewer = user.profile
    base = build_eligible_queryset(user)
    total_available = base.count()
    if total_available == 0:
        return DiscoverResult(profiles=[], expanded_search=False, relaxation_stage="empty")

    stages = build_search_stages(viewer)
    best_ranked: list[ScoredProfile] = []
    best_stage = "strict"

    for stage_name, config in stages:
        ranked = _rank_candidates(viewer, base, config)
        if len(ranked) >= MIN_RESULTS_BEFORE_RELAX:
            profiles = [row.profile for row in ranked[:RESULT_LIMIT]]
            return DiscoverResult(
                profiles=profiles,
                expanded_search=stage_name != "strict",
                relaxation_stage=stage_name,
                meta={"available_pool": total_available, "stage_count": len(ranked)},
            )
        if len(ranked) > len(best_ranked):
            best_ranked = ranked
            best_stage = stage_name

    profiles = [row.profile for row in best_ranked[:RESULT_LIMIT]]
    return DiscoverResult(
        profiles=profiles,
        expanded_search=best_stage != "strict" or len(profiles) > 0,
        relaxation_stage=best_stage,
        meta={"available_pool": total_available, "stage_count": len(best_ranked)},
    )


def rank_discover_profiles(user) -> list[Profile]:
    """Backward-compatible helper used by legacy imports."""
    return discover_profiles(user).profiles
