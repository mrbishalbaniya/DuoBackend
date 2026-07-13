"""Track active WebSocket connections per user (Redis cache)."""

from __future__ import annotations

import logging
import time
from typing import Any

from django.core.cache import cache

logger = logging.getLogger("duo.realtime")

CONNECTION_TTL = 120
HEARTBEAT_TIMEOUT = 90
MAX_CONNECTIONS_PER_USER = 12


def _key(user_id: int) -> str:
    return f"ws:connections:{user_id}"


def register_connection(user_id: int, channel_name: str, *, socket_type: str) -> bool:
    """Register a connection. Returns False when the per-user limit is exceeded."""
    try:
        connections: dict[str, Any] = cache.get(_key(user_id)) or {}
        now = int(time.time())
        alive = {
            k: v
            for k, v in connections.items()
            if now - int(v.get("last_seen", 0)) < HEARTBEAT_TIMEOUT
        }
        if channel_name not in alive and len(alive) >= MAX_CONNECTIONS_PER_USER:
            logger.warning("ws_connection_limit user_id=%s type=%s", user_id, socket_type)
            return False
        alive[channel_name] = {
            "type": socket_type,
            "connected_at": now,
            "last_seen": now,
        }
        cache.set(_key(user_id), alive, CONNECTION_TTL)
        return True
    except Exception as exc:
        logger.debug("ws_register_failed user_id=%s error=%s", user_id, exc)
        from django.conf import settings

        return settings.DEBUG


def touch_connection(user_id: int, channel_name: str) -> None:
    try:
        connections: dict[str, Any] = cache.get(_key(user_id)) or {}
        if channel_name in connections:
            connections[channel_name]["last_seen"] = int(time.time())
            cache.set(_key(user_id), connections, CONNECTION_TTL)
    except Exception:
        pass


def unregister_connection(user_id: int, channel_name: str) -> None:
    try:
        connections: dict[str, Any] = cache.get(_key(user_id)) or {}
        connections.pop(channel_name, None)
        if connections:
            cache.set(_key(user_id), connections, CONNECTION_TTL)
        else:
            cache.delete(_key(user_id))
    except Exception:
        pass


def connection_count(user_id: int) -> int:
    try:
        connections: dict[str, Any] = cache.get(_key(user_id)) or {}
        now = int(time.time())
        alive = {
            k
            for k, v in connections.items()
            if now - int(v.get("last_seen", 0)) < HEARTBEAT_TIMEOUT
        }
        return len(alive)
    except Exception:
        return 0
