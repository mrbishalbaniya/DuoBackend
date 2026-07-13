"""Central cache invalidation helpers."""

from __future__ import annotations

import logging

from duo_project.cache import keys
from duo_project.cache.service import api_cache

logger = logging.getLogger("duo.cache")


def get_user_cache_version(user_id: int) -> int:
    version = api_cache.get(keys.user_cache_version(user_id), label="user_version")
    if version is None:
        api_cache.set(keys.user_cache_version(user_id), 1, ttl=None, label="user_version")
        return 1
    return int(version)


def bump_user_cache_version(user_id: int, *, reason: str = "") -> int:
    version = api_cache.incr(keys.user_cache_version(user_id), label="user_version")
    logger.info("cache_version_bump user_id=%s version=%s reason=%s", user_id, version, reason or "-")
    return version


def invalidate_user_caches(user_id: int, *, reason: str = "") -> None:
    """Bump version so all user-scoped list caches miss on next request."""
    bump_user_cache_version(user_id, reason=reason)
    api_cache.delete(keys.user(user_id), label="user")
    api_cache.delete(keys.unread_count(user_id), label="unread")
    api_cache.delete(keys.presence(user_id), label="presence")


def invalidate_profile_caches(profile_id: int, user_id: int, *, reason: str = "") -> None:
    invalidate_user_caches(user_id, reason=reason or "profile")
    api_cache.delete(keys.profile(profile_id), label="profile")


def invalidate_subscription_plans() -> None:
    api_cache.delete(keys.subscription_plans(), label="subscription_plans")


def invalidate_conversation_for_users(conversation_id: int, user_ids: list[int], *, reason: str = "") -> None:
    for uid in user_ids:
        invalidate_user_caches(uid, reason=reason or "conversation")
        api_cache.delete(keys.conversation_meta(conversation_id, uid), label="conversation_meta")


def invalidate_match_users(user1_id: int, user2_id: int, *, reason: str = "") -> None:
    invalidate_user_caches(user1_id, reason=reason or "match")
    invalidate_user_caches(user2_id, reason=reason or "match")
