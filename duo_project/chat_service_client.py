"""HTTP client for the standalone chat-service (DuoBackend/chat-service).

Keeps chat-service's shadow `users`/`matches` tables in sync with this
monolith's authoritative data. Called from Celery tasks
(duo_project/tasks/chat_sync.py) via signal receivers in
duo_project/realtime/signals.py — never called synchronously from a request
path, so a chat-service outage never blocks a swipe/match/profile save.

See chat-service/README.md for the full sync contract.
"""

from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger("duo.chat_service")

_TIMEOUT = 5


def _enabled() -> bool:
    return bool(settings.CHAT_SERVICE_URL and settings.CHAT_INTERNAL_TOKEN)


def _post(path: str, payload: dict) -> None:
    if not _enabled():
        return
    url = settings.CHAT_SERVICE_URL.rstrip("/") + path
    try:
        response = requests.post(
            url,
            json=payload,
            timeout=_TIMEOUT,
            headers={"Authorization": f"Bearer {settings.CHAT_INTERNAL_TOKEN}"},
        )
        response.raise_for_status()
    except requests.exceptions.RequestException:
        logger.warning("chat_service_sync_failed url=%s", url, exc_info=True)


def _delete(path: str) -> None:
    if not _enabled():
        return
    url = settings.CHAT_SERVICE_URL.rstrip("/") + path
    try:
        response = requests.delete(
            url,
            timeout=_TIMEOUT,
            headers={"Authorization": f"Bearer {settings.CHAT_INTERNAL_TOKEN}"},
        )
        response.raise_for_status()
    except requests.exceptions.RequestException:
        logger.warning("chat_service_sync_failed url=%s", url, exc_info=True)


def sync_user(user_id: int) -> None:
    from django.contrib.auth.models import User

    try:
        user = User.objects.select_related("profile").get(id=user_id)
    except User.DoesNotExist:
        return
    profile = getattr(user, "profile", None)
    _post(
        "/internal/users/sync",
        {
            "id": user.id,
            "username": user.username,
            "full_name": (getattr(profile, "full_name", "") or user.get_full_name() or user.username),
            "photo_url": getattr(profile, "photo_url", "") or "",
        },
    )


def sync_match(match_id: int) -> None:
    from matching.models import Match

    try:
        match = Match.objects.get(id=match_id)
    except Match.DoesNotExist:
        return
    _post(
        "/internal/matches/sync",
        {
            "id": match.id,
            "user1_id": match.user1_id,
            "user2_id": match.user2_id,
            "matched_at": match.matched_at.isoformat(),
        },
    )


def delete_match(match_id: int) -> None:
    _delete(f"/internal/matches/{match_id}")
