"""Central notification dispatch service."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from django.conf import settings

from duo_project.cache.presence import is_online
from duo_project.cache.service import api_cache
from notifications.constants import CHAT_MESSAGE
from notifications.models import PushDeliveryLog
from notifications.services.fcm import FCMService
from notifications.services.preferences import can_send_push, get_preferences

logger = logging.getLogger("duo.notifications")

_DEDUP_TTL_SECONDS = 30


def _dedup_key(user_id: int, notification_type: str, tag: str, body: str) -> str:
    raw = f"{user_id}:{notification_type}:{tag}:{body[:120]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _is_duplicate(user_id: int, notification_type: str, tag: str, body: str) -> bool:
    key = f"push:dedup:{_dedup_key(user_id, notification_type, tag, body)}"
    if api_cache.get(key, label="push_dedup"):
        return True
    api_cache.set(key, True, _DEDUP_TTL_SECONDS, label="push_dedup")
    return False


def _log_delivery(
    *,
    user_id: int,
    notification_type: str,
    title: str,
    body: str,
    status: str,
    devices_targeted: int = 0,
    devices_sent: int = 0,
    skip_reason: str = "",
    error_message: str = "",
    payload: dict | None = None,
) -> None:
    try:
        PushDeliveryLog.objects.create(
            user_id=user_id,
            notification_type=notification_type,
            title=title[:255],
            body=body,
            status=status,
            devices_targeted=devices_targeted,
            devices_sent=devices_sent,
            skip_reason=skip_reason[:255],
            error_message=error_message[:2000],
            payload=payload or {},
        )
    except Exception:
        logger.debug("push_delivery_log_write_failed user_id=%s", user_id)


def send_push_notification(
    *,
    user_id: int,
    notification_type: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
    link: str = "",
    icon: str = "",
    image: str = "",
    tag: str = "",
    badge: str = "",
    skip_if_online: bool = False,
    respect_preferences: bool = True,
    deduplicate: bool = True,
    broadcast_ws: bool = True,
) -> int:
    """
    Send push to all active devices for a user.
    Returns number of devices successfully notified.
    """
    payload = dict(data or {})
    payload.setdefault("type", notification_type)

    if deduplicate and _is_duplicate(user_id, notification_type, tag, body):
        _log_delivery(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            body=body,
            status=PushDeliveryLog.STATUS_SKIPPED,
            skip_reason="duplicate",
            payload=payload,
        )
        return 0

    if respect_preferences:
        allowed, reason = can_send_push_by_id(user_id, notification_type)
        if not allowed:
            _log_delivery(
                user_id=user_id,
                notification_type=notification_type,
                title=title,
                body=body,
                status=PushDeliveryLog.STATUS_SKIPPED,
                skip_reason=reason,
                payload=payload,
            )
            return 0

    if skip_if_online and notification_type == CHAT_MESSAGE and is_online(user_id):
        _log_delivery(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            body=body,
            status=PushDeliveryLog.STATUS_SKIPPED,
            skip_reason="user_online",
            payload=payload,
        )
        if broadcast_ws:
            _broadcast_ws(user_id, title, body, payload)
        return 0

    prefs = get_preferences_by_id(user_id)
    sound_enabled = prefs.sound_enabled if prefs else True
    vibration_enabled = prefs.vibration_enabled if prefs else True

    service = FCMService()
    devices_targeted = 0
    devices_sent = 0

    if service.is_configured():
        devices_targeted, devices_sent = service.send_to_user(
            user_id,
            title=title,
            body=body,
            data=payload,
            link=link,
            icon=icon,
            image=image,
            tag=tag,
            badge=badge,
            sound_enabled=sound_enabled,
            vibration_enabled=vibration_enabled,
        )
    else:
        _log_delivery(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            body=body,
            status=PushDeliveryLog.STATUS_SKIPPED,
            skip_reason="fcm_not_configured",
            payload=payload,
        )
        if broadcast_ws:
            _broadcast_ws(user_id, title, body, payload)
        return 0

    status = (
        PushDeliveryLog.STATUS_SENT
        if devices_sent > 0
        else PushDeliveryLog.STATUS_FAILED
    )
    _log_delivery(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        body=body,
        status=status,
        devices_targeted=devices_targeted,
        devices_sent=devices_sent,
        error_message="" if devices_sent else "no_devices_delivered",
        payload=payload,
    )

    if broadcast_ws:
        _broadcast_ws(user_id, title, body, payload)

    return devices_sent


def send_push_to_users(
    user_ids: list[int],
    *,
    notification_type: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
    link: str = "",
    icon: str = "",
    tag: str = "",
    respect_preferences: bool = True,
) -> int:
    total = 0
    for uid in user_ids:
        total += send_push_notification(
            user_id=uid,
            notification_type=notification_type,
            title=title,
            body=body,
            data=data,
            link=link,
            icon=icon,
            tag=tag,
            respect_preferences=respect_preferences,
            deduplicate=False,
        )
    return total


def _broadcast_ws(user_id: int, title: str, body: str, data: dict[str, str]) -> None:
    try:
        from duo_project.realtime.broadcast import broadcast_notification

        broadcast_notification(user_id=user_id, title=title, body=body, data=data)
    except Exception:
        logger.debug("ws_notification_broadcast_failed user_id=%s", user_id)


def can_send_push_by_id(user_id: int, notification_type: str) -> tuple[bool, str]:
    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return False, "user_not_found"
    return can_send_push(user, notification_type)


def get_preferences_by_id(user_id: int):
    from notifications.models import NotificationPreference

    return NotificationPreference.objects.filter(user_id=user_id).first()


def _frontend_url() -> str:
    return getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")


def default_icon_url() -> str:
    return f"{_frontend_url()}/icon"


def default_badge_url() -> str:
    return f"{_frontend_url()}/icon"
