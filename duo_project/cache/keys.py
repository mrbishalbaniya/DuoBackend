"""Consistent Redis cache key naming."""

from __future__ import annotations

PREFIX = "v1"


def _join(*parts: str | int) -> str:
    return ":".join(str(p) for p in parts if p is not None and str(p) != "")


def user(user_id: int) -> str:
    return _join("user", user_id)


def user_cache_version(user_id: int) -> str:
    return _join("user", user_id, "cache_version")


def profile(profile_id: int) -> str:
    return _join("profile", profile_id)


def profile_public(profile_id: int, viewer_id: int, owner_version: int) -> str:
    return _join("profile", profile_id, "viewer", viewer_id, "v", owner_version)


def discover(user_id: int, version: int) -> str:
    return _join("discover", user_id, "v", version)


def matches(user_id: int, version: int, limit: str, offset: str) -> str:
    return _join("matches", user_id, "v", version, "l", limit, "o", offset)


def liked_by_you(user_id: int, version: int, limit: str, offset: str) -> str:
    return _join("likes", "out", user_id, "v", version, "l", limit, "o", offset)


def likes_you(user_id: int, version: int, limit: str, offset: str) -> str:
    return _join("likes", "in", user_id, "v", version, "l", limit, "o", offset)


def profile_visitors(user_id: int, version: int, limit: str, offset: str) -> str:
    return _join("visitors", user_id, "v", version, "l", limit, "o", offset)


def skipped_by_you(user_id: int, version: int, limit: str, offset: str) -> str:
    return _join("skipped", user_id, "v", version, "l", limit, "o", offset)


def match_insight(match_id: int, user_id: int) -> str:
    return _join("match", "insight", match_id, user_id)


def conversations(
    user_id: int,
    version: int,
    *,
    archived: bool,
    unread: bool,
    limit: str,
    offset: str,
) -> str:
    return _join(
        "conversations",
        user_id,
        "v",
        version,
        "a",
        int(archived),
        "u",
        int(unread),
        "l",
        limit,
        "o",
        offset,
    )


def conversation_meta(conversation_id: int, user_id: int) -> str:
    return _join("conversation", conversation_id, "user", user_id)


def unread_count(user_id: int) -> str:
    return _join("notifications", "unread", user_id)


def subscription_plans() -> str:
    return _join("subscription", "plans")


def subscription_status(user_id: int, version: int) -> str:
    return _join("subscription", "status", user_id, "v", version)


def wallet_summary(user_id: int, version: int) -> str:
    return _join("wallet", user_id, "v", version)


def static_lookups() -> str:
    return _join("static", "lookups")


def presence(user_id: int) -> str:
    return _join("presence", user_id)


def typing(conversation_id: str, user_id: int) -> str:
    return _join("typing", conversation_id, user_id)


def avatar(user_id: int) -> str:
    return _join("avatar", user_id)


def security_events(user_id: int, version: int, unread_only: bool) -> str:
    return _join("security", "events", user_id, "v", version, "u", int(unread_only))


def list_window_suffix(request) -> tuple[str, str]:
    limit = request.query_params.get("limit", "")
    offset = request.query_params.get("offset", "")
    return str(limit), str(offset)
