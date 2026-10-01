"""Matching domain helpers."""

from __future__ import annotations

import logging

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q

from chat.models import Conversation
from chat.services import users_are_blocked
from duo_project.cache.invalidation import invalidate_user_caches
from matching.compatibility import compute_compatibility
from matching.models import Match, Swipe

logger = logging.getLogger("duo.matching")


def get_existing_match(user_a: User, user_b: User) -> Match | None:
    return Match.objects.filter(
        Q(user1=user_a, user2=user_b) | Q(user1=user_b, user2=user_a)
    ).first()


def ensure_mutual_likes(user_a: User, user_b: User) -> None:
    """Upsert reciprocal LIKE swipes so the pair looks like a normal mutual match."""
    Swipe.objects.update_or_create(
        from_user=user_a,
        to_user=user_b,
        defaults={"action": "LIKE"},
    )
    Swipe.objects.update_or_create(
        from_user=user_b,
        to_user=user_a,
        defaults={"action": "LIKE"},
    )


def match_fields(user1: User, user2: User, compatibility_score: int | None = None) -> dict:
    """Compatibility scores and insights for a new match, computed from both profiles.

    An admin-chosen overall score (admin "create match" form) overrides only the
    overall number; the four dimension scores are always computed.
    """
    p1 = getattr(user1, "profile", None)
    p2 = getattr(user2, "profile", None)
    if p1 is None or p2 is None:
        fields = {"compatibility_score": 50, "values_score": 50, "lifestyle_score": 50, "career_score": 50,
                  "hobbies_score": 50, "shared_interests": [], "spark_factors": [],
                  "vision_insight": "", "communication_insight": ""}
    else:
        fields = compute_compatibility(p1, p2).as_match_fields()
    if compatibility_score is not None:
        fields["compatibility_score"] = max(0, min(100, int(compatibility_score)))
    return fields


def create_match_between(
    user1: User,
    user2: User,
    *,
    compatibility_score: int | None = None,
    ensure_likes: bool = True,
    notify: bool = True,
    allow_blocked: bool = False,
) -> tuple[Match, bool]:
    """
    Create a Match + Conversation between two users.

    Returns (match, created).
    """
    if user1.id == user2.id:
        raise ValueError("Cannot match a user with themselves.")

    if not allow_blocked and users_are_blocked(user1, user2):
        raise ValueError("These users have blocked each other.")

    existing = get_existing_match(user1, user2)
    if existing:
        Conversation.objects.get_or_create(match=existing)
        return existing, False

    fields = match_fields(user1, user2, compatibility_score)

    with transaction.atomic():
        if ensure_likes:
            ensure_mutual_likes(user1, user2)

        match = Match.objects.create(user1=user1, user2=user2, **fields)
        Conversation.objects.get_or_create(match=match)

    invalidate_user_caches(user1.id, reason="admin_match")
    invalidate_user_caches(user2.id, reason="admin_match")

    if notify:
        try:
            from notifications.dispatch import dispatch_match_push

            dispatch_match_push(match=match)
        except Exception:
            logger.exception("admin_match_notify_failed match_id=%s", match.id)

    logger.info(
        "admin_match_created match_id=%s user1=%s user2=%s score=%s",
        match.id,
        user1.id,
        user2.id,
        match.compatibility_score,
    )
    return match, True
