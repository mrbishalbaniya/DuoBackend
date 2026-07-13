"""User presence and typing indicators in Redis."""

from __future__ import annotations

import time

from duo_project.cache import keys, ttl
from duo_project.cache.service import api_cache


def mark_online(user_id: int) -> None:
    api_cache.set(
        keys.presence(user_id),
        {"online": True, "ts": int(time.time())},
        ttl.PRESENCE,
        label="presence",
    )


def is_online(user_id: int) -> bool:
    payload = api_cache.get(keys.presence(user_id), label="presence")
    return bool(payload and payload.get("online"))


def set_typing(conversation_id: str, user_id: int) -> None:
    api_cache.set(
        keys.typing(conversation_id, user_id),
        {"typing": True, "ts": int(time.time())},
        ttl.TYPING,
        label="typing",
    )


def is_typing(conversation_id: str, user_id: int) -> bool:
    payload = api_cache.get(keys.typing(conversation_id, user_id), label="typing")
    if not payload:
        return False
    ts = int(payload.get("ts") or 0)
    return (time.time() - ts) < ttl.TYPING
