"""Matching domain helpers."""

from __future__ import annotations

import logging
import random

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q

from chat.models import Conversation
from chat.services import users_are_blocked
from duo_project.cache.invalidation import invalidate_user_caches
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


def _default_scores(compatibility_score: int | None = None) -> dict:
    values = random.randint(75, 98)
    lifestyle = random.randint(60, 95)
    career = random.randint(65, 95)
    hobbies = random.randint(50, 90)
    overall = compatibility_score
    if overall is None:
        overall = int((values * 0.35) + (lifestyle * 0.25) + (career * 0.25) + (hobbies * 0.15))
    overall = max(0, min(100, int(overall)))
    return {
        "compatibility_score": overall,
        "values_score": values,
        "lifestyle_score": lifestyle,
        "career_score": career,
        "hobbies_score": hobbies,
    }


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

    scores = _default_scores(compatibility_score)
    all_interests = [
        "Hiking",
        "Reading",
        "Cooking",
        "Travel",
        "Music",
        "Yoga",
        "Photography",
        "Dancing",
        "Classic Rock",
        "Philanthropy",
    ]
    shared = random.sample(all_interests, random.randint(3, 6))
    sparks = [
        "Both passionate about adventure travel and mountains",
        "Strong mutual focus on family-oriented celebrations",
        "Shared appreciation for traditional cultural values",
        "Admin-curated pairing for a meaningful connection",
    ]
    p1_name = getattr(getattr(user1, "profile", None), "full_name", None) or user1.username
    p2_name = getattr(getattr(user2, "profile", None), "full_name", None) or user2.username

    with transaction.atomic():
        if ensure_likes:
            ensure_mutual_likes(user1, user2)

        match = Match.objects.create(
            user1=user1,
            user2=user2,
            compatibility_score=scores["compatibility_score"],
            values_score=scores["values_score"],
            lifestyle_score=scores["lifestyle_score"],
            career_score=scores["career_score"],
            hobbies_score=scores["hobbies_score"],
            spark_factors=random.sample(sparks, 2),
            shared_interests=shared,
            vision_insight=(
                "Both express a desire for an urban lifestyle while maintaining strong ties "
                "to traditional ancestral homes during festivals. This alignment ensures no "
                "geographical friction in the coming years."
            ),
            communication_insight=(
                f"{p1_name} values directness and logic, while {p2_name} prioritizes emotional "
                "resonance. This balanced pairing often results in highly effective problem-solving "
                "in partnerships."
            ),
        )
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
