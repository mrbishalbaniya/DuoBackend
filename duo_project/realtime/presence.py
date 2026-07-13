"""Online presence and last-seen tracking."""

from __future__ import annotations

import time
from typing import Any

from django.core.cache import cache

PRESENCE_TTL = 30
IDLE_AFTER = 60


def _key(user_id: int) -> str:
    return f"presence:{user_id}"


def mark_active(user_id: int, *, status: str = "online") -> dict[str, Any]:
    now = int(time.time())
    payload = {
        "status": status,
        "last_seen": now,
        "updated_at": now,
    }
    try:
        cache.set(_key(user_id), payload, PRESENCE_TTL)
    except Exception:
        pass
    return payload


def mark_offline(user_id: int) -> dict[str, Any]:
    now = int(time.time())
    payload = {"status": "offline", "last_seen": now, "updated_at": now}
    try:
        cache.set(_key(user_id), payload, 3600)
    except Exception:
        pass
    return payload


def mark_ringing(user_id: int) -> dict[str, Any]:
    return mark_active(user_id, status="ringing")


def mark_in_call(user_id: int) -> dict[str, Any]:
    return mark_active(user_id, status="in_call")


def clear_call_presence(user_id: int) -> dict[str, Any]:
    return mark_active(user_id, status="online")


def get_presence(user_id: int) -> dict[str, Any]:
    try:
        payload = cache.get(_key(user_id))
        if not payload:
            return {"status": "offline", "last_seen": None}
        now = int(time.time())
        last_seen = int(payload.get("last_seen", 0))
        if now - last_seen > PRESENCE_TTL:
            return {"status": "offline", "last_seen": last_seen}
        if now - last_seen > IDLE_AFTER:
            return {"status": "idle", "last_seen": last_seen}
        return {"status": payload.get("status", "online"), "last_seen": last_seen}
    except Exception:
        return {"status": "offline", "last_seen": None}
