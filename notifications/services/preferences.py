"""User notification preference helpers."""

from __future__ import annotations

from notifications.constants import PREFERENCE_FIELD_BY_TYPE
from notifications.models import NotificationPreference


def get_preferences(user) -> NotificationPreference:
    prefs, _ = NotificationPreference.objects.get_or_create(user=user)
    return prefs


def can_send_push(user, notification_type: str) -> tuple[bool, str]:
    """Return (allowed, skip_reason)."""
    prefs = get_preferences(user)
    if not prefs.push_enabled:
        return False, "push_disabled"

    field = PREFERENCE_FIELD_BY_TYPE.get(notification_type)
    if field and not getattr(prefs, field, True):
        return False, f"{field}_disabled"

    return True, ""


def preference_payload(prefs: NotificationPreference) -> dict:
    return {
        "push_enabled": prefs.push_enabled,
        "chat_enabled": prefs.chat_enabled,
        "calls_enabled": prefs.calls_enabled,
        "match_enabled": prefs.match_enabled,
        "likes_enabled": prefs.likes_enabled,
        "marketing_enabled": prefs.marketing_enabled,
        "announcements_enabled": prefs.announcements_enabled,
        "verification_enabled": prefs.verification_enabled,
        "payment_enabled": prefs.payment_enabled,
        "sound_enabled": prefs.sound_enabled,
        "vibration_enabled": prefs.vibration_enabled,
    }
