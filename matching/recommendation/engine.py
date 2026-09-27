from __future__ import annotations

from dataclasses import replace

from django.db.models import QuerySet

from accounts.models import Profile

from matching.recommendation.fallback import build_search_stages, stage_expansions
from matching.recommendation.queries import (
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
RECYCLED_PENALTY = 25.0


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
            score -= RECYCLED_PENALTY
        ranked.append(ScoredProfile(profile=candidate, score=score, distance_km=distance))

    ranked.sort(key=lambda row: (-row.score, row.distance_km, row.profile.id))
    return ranked


def _best_stage(
    viewer: Profile,
    queryset: QuerySet[Profile],
    stages: list[tuple[str, SearchConfig]],
) -> tuple[str, SearchConfig, list[ScoredProfile]]:
    """First stage with enough people, else the stage that found the most."""
    best: tuple[str, SearchConfig, list[ScoredProfile]] | None = None
    for stage_name, config in stages:
        ranked = _rank_candidates(viewer, queryset, config)
        if len(ranked) >= MIN_RESULTS_BEFORE_RELAX:
            return stage_name, config, ranked
        if best is None or len(ranked) > len(best[2]):
            best = (stage_name, config, ranked)
    return best if best is not None else (stages[0][0], stages[0][1], [])


def discover_profiles(user) -> DiscoverResult:
    """Profiles for the swipe deck, always within the viewer's filters.

    Order: people the viewer hasn't swiped yet, then (only if that runs short)
    people they skipped before. Liked, matched and blocked people never return.
    """
    viewer = user.profile
    stages = build_search_stages(viewer)
    strict_config = stages[0][1]

    fresh_pool = build_eligible_queryset(user)
    stage_name, stage_config, ranked = _best_stage(viewer, fresh_pool, stages)
    rows = ranked[:RESULT_LIMIT]
    expansions = stage_expansions(strict_config, stage_config) if rows else []

    used_recycled = False
    if len(rows) < MIN_RESULTS_BEFORE_RELAX:
        recycled_stages = [(name, replace(config, recycled_skips=True)) for name, config in stages]
        recycled_name, recycled_config, recycled = _best_stage(
            viewer, build_recycled_queryset(user), recycled_stages
        )
        seen = {row.profile.id for row in rows}
        extra = [row for row in recycled if row.profile.id not in seen]
        if extra:
            used_recycled = True
            rows = (rows + extra)[:RESULT_LIMIT]
            for reason in stage_expansions(strict_config, recycled_config):
                if reason not in expansions:
                    expansions.append(reason)
            if not ranked:
                stage_name = recycled_name

    for row in rows:
        # Read by ProfileSerializer.get_distance_km (rounded there for privacy).
        row.profile.discover_distance_km = row.distance_km

    return DiscoverResult(
        profiles=[row.profile for row in rows],
        expanded_search=bool(expansions),
        relaxation_stage=stage_name,
        recycled_skips=used_recycled,
        meta={
            "fresh_found": len(ranked),
            "expansions": expansions,
        },
    )


def rank_discover_profiles(user) -> list[Profile]:
    """Backward-compatible helper used by legacy imports."""
    return discover_profiles(user).profiles
