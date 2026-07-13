"""Backward-compatible discovery entrypoints."""

from matching.recommendation.engine import discover_profiles, rank_discover_profiles
from matching.recommendation.queries import build_eligible_queryset
from matching.recommendation.scoring import passes_hard_filters

# Legacy names used in tests/admin tooling.
build_discover_queryset = build_eligible_queryset


def apply_user_filters(queryset, viewer):
    """Legacy helper — strict stage config only."""
    from matching.recommendation.fallback import build_search_stages

    config = build_search_stages(viewer)[0][1]
    filtered_ids = []
    from matching.recommendation.scoring import candidate_distance_km, viewer_anchor

    _, viewer_coords = viewer_anchor(viewer)
    for candidate in queryset[:400]:
        distance = candidate_distance_km(viewer_coords, candidate)
        if passes_hard_filters(viewer, candidate, config, distance_km=distance):
            filtered_ids.append(candidate.id)
    return queryset.filter(id__in=filtered_ids)
