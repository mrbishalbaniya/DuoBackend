from __future__ import annotations

from django.db.models import Count, Q, QuerySet

from accounts.models import Profile
from duo_project.query_optimization import get_matched_user_ids
from duo_project.security.privacy import blocked_user_ids
from matching.models import Swipe


def _annotated_profiles() -> QuerySet[Profile]:
    return Profile.objects.select_related("user").annotate(
        likes_received_count=Count(
            "user__swipes_received",
            filter=Q(user__swipes_received__action__in=["LIKE", "SUPERLIKE"]),
            distinct=True,
        ),
        matches_as_user1_count=Count("user__matches_as_user1", distinct=True),
        matches_as_user2_count=Count("user__matches_as_user2", distinct=True),
    )


def build_eligible_queryset(user) -> QuerySet[Profile]:
    """Fresh discover pool: excludes self, swiped, matched, blocked, not onboarded."""
    swiped_ids = Swipe.objects.filter(from_user=user).values_list("to_user_id", flat=True)
    matched_ids = get_matched_user_ids(user)
    blocked = blocked_user_ids(user.id)

    return (
        _annotated_profiles()
        .exclude(user=user)
        .exclude(user_id__in=swiped_ids)
        .exclude(user_id__in=matched_ids)
        .exclude(user_id__in=blocked)
        .filter(is_onboarded=True)
    )


def build_recycled_queryset(user) -> QuerySet[Profile]:
    """Re-surface previously skipped profiles when the fresh pool is empty."""
    matched_ids = get_matched_user_ids(user)
    blocked = blocked_user_ids(user.id)

    return (
        _annotated_profiles()
        .exclude(user=user)
        .exclude(user_id__in=matched_ids)
        .exclude(user_id__in=blocked)
        .filter(is_onboarded=True)
    )


def build_broad_queryset(user) -> QuerySet[Profile]:
    """Last-resort pool: any profile except self, matches, and blocks."""
    matched_ids = get_matched_user_ids(user)
    blocked = blocked_user_ids(user.id)

    return (
        _annotated_profiles()
        .exclude(user=user)
        .exclude(user_id__in=matched_ids)
        .exclude(user_id__in=blocked)
    )
