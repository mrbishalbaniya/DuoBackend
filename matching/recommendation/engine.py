from __future__ import annotations

from django.db.models import QuerySet

from accounts.models import Profile

from matching.recommendation.fallback import build_search_stages
from matching.recommendation.queries import (
    build_broad_queryset,
    build_eligible_queryset,
    build_recycled_queryset,
)
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
        if config.recycled_skips:
            score -= 25.0
        ranked.append(ScoredProfile(profile=candidate, score=score, distance_km=distance))

    ranked.sort(key=lambda row: (-row.score, row.distance_km, row.profile.id))
    return ranked


def _resolve_pool(user, config: SearchConfig) -> QuerySet[Profile]:
    if config.recycled_skips:
        return build_recycled_queryset(user)
    return build_eligible_queryset(user)


def discover_profiles(user) -> DiscoverResult:
    viewer = user.profile
    fresh_pool = build_eligible_queryset(user)
    total_fresh = fresh_pool.count()

    pools: list[tuple[str, QuerySet[Profile], bool]] = [
        ("fresh", fresh_pool, False),
    ]
    if total_fresh == 0:
        recycled_pool = build_recycled_queryset(user)
        if recycled_pool.exists():
            pools.append(("recycled", recycled_pool, True))

    broad_pool = build_broad_queryset(user)
    if broad_pool.exists():
        pools.append(("broad", broad_pool, False))

    stages = build_search_stages(viewer)
    best_ranked: list[ScoredProfile] = []
    best_stage = "strict"
    used_recycled = False

    for pool_name, queryset, recycled in pools:
        for stage_name, config in stages:
            stage_config = config
            if recycled and not config.recycled_skips:
                stage_config = SearchConfig(
                    age_min=config.age_min,
                    age_max=config.age_max,
                    max_distance_km=config.max_distance_km,
                    location_pref=config.location_pref,
                    apply_location=config.apply_location,
                    gender=config.gender,
                    relationship_goal=config.relationship_goal,
                    verified_only=config.verified_only,
                    prefer_verified=config.prefer_verified,
                    prefer_active=config.prefer_active,
                    prefer_popular=config.prefer_popular,
                    prefer_new=config.prefer_new,
                    ignore_distance=config.ignore_distance,
                    recycled_skips=True,
                )

            ranked = _rank_candidates(viewer, queryset, stage_config)
            if len(ranked) >= MIN_RESULTS_BEFORE_RELAX:
                profiles = [row.profile for row in ranked[:RESULT_LIMIT]]
                expanded = stage_name != "strict" or recycled or pool_name != "fresh"
                return DiscoverResult(
                    profiles=profiles,
                    expanded_search=expanded,
                    relaxation_stage=stage_name if pool_name == "fresh" else f"{pool_name}_{stage_name}",
                    recycled_skips=recycled or stage_config.recycled_skips,
                    meta={
                        "pool": pool_name,
                        "fresh_pool": total_fresh,
                        "stage_count": len(ranked),
                    },
                )
            if len(ranked) > len(best_ranked):
                best_ranked = ranked
                best_stage = stage_name if pool_name == "fresh" else f"{pool_name}_{stage_name}"
                used_recycled = recycled or stage_config.recycled_skips

    profiles = [row.profile for row in best_ranked[:RESULT_LIMIT]]
    return DiscoverResult(
        profiles=profiles,
        expanded_search=best_stage != "strict" or used_recycled or len(profiles) > 0,
        relaxation_stage=best_stage,
        recycled_skips=used_recycled,
        meta={"fresh_pool": total_fresh, "stage_count": len(best_ranked)},
    )


def rank_discover_profiles(user) -> list[Profile]:
    """Backward-compatible helper used by legacy imports."""
    return discover_profiles(user).profiles
