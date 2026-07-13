"""WebSocket event rate limiting (Redis-backed with in-memory fallback)."""

from __future__ import annotations

import logging
import time

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("duo.realtime")

# Per-user per-event-type limits (events per window)
LIMITS: dict[str, tuple[int, int]] = {
    "typing": (8, 10),  # 8 events / 10 seconds
    "chat_message": (30, 10),
    "recording": (8, 10),
    "upload_progress": (20, 10),
    "ping": (60, 60),
    "call_offer": (30, 60),
    "call_answer": (30, 60),
    "ice_candidate": (120, 60),
    "call_invite": (10, 60),
    "call_hangup": (20, 60),
    "default": (120, 10),
}


def allow_event(user_id: int, event_type: str) -> bool:
    """Return False when the user exceeds the rate limit for this event type."""
    event_type = (event_type or "default").strip().lower()
    max_events, window = LIMITS.get(event_type, LIMITS["default"])
    bucket = int(time.time()) // window
    key = f"ws:throttle:{user_id}:{event_type}:{bucket}"
    try:
        count = cache.get(key, 0)
        if count >= max_events:
            logger.warning("ws_rate_limited user_id=%s event=%s", user_id, event_type)
            return False
        cache.set(key, int(count) + 1, window + 1)
        return True
    except Exception:
        if settings.DEBUG:
            return True
        logger.warning("ws_throttle_cache_error user_id=%s event=%s", user_id, event_type)
        return False
