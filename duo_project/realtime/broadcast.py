"""Central channel-layer broadcast helpers."""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from duo_project.realtime.groups import activity_feed, chat_room, user_inbox

logger = logging.getLogger("duo.realtime")


def _send_group(group: str, event: dict) -> None:
    layer = get_channel_layer()
    if not layer:
        return
    try:
        async_to_sync(layer.group_send)(group, event)
    except Exception as exc:
        logger.warning("broadcast_failed group=%s error=%s", group, exc)


def broadcast_to_user(user_id: int, event_type: str, payload: dict[str, Any] | None = None) -> None:
    _send_group(
        user_inbox(user_id),
        {
            "type": "inbox.event",
            "event_type": event_type,
            "payload": payload or {},
        },
    )


def broadcast_to_chat(conversation_id: str | int, handler: str, **fields) -> None:
    _send_group(chat_room(conversation_id), {"type": handler, **fields})


def broadcast_activity_refresh() -> None:
    _send_group(activity_feed(), {"type": "activity.refresh"})


def broadcast_match_event(*, match, conversation_public_id: str | None = None) -> None:
    score = int(getattr(match, "compatibility_score", 0) or 0)
    base = {
        "match_id": match.id,
        "compatibility_score": score,
        "conversation_id": conversation_public_id or "",
        "matched_at": match.matched_at.isoformat() if match.matched_at else "",
    }
    for user, other in ((match.user1, match.user2), (match.user2, match.user1)):
        broadcast_to_user(
            user.id,
            "match_created",
            {
                **base,
                "other_user_id": other.id,
            },
        )


def broadcast_like_event(*, from_user_id: int, to_user_id: int, action: str) -> None:
    event_type = "superlike_received" if action == "SUPERLIKE" else "like_received"
    broadcast_to_user(
        to_user_id,
        event_type,
        {
            "from_user_id": from_user_id,
            "action": action,
        },
    )


def broadcast_profile_viewed(*, viewer_id: int, viewed_user_id: int) -> None:
    broadcast_to_user(
        viewed_user_id,
        "profile_viewed",
        {"viewer_id": viewer_id},
    )


def broadcast_conversation_updated(
    *,
    user_ids: list[int],
    conversation_public_id: str,
    last_message: dict | None = None,
) -> None:
    payload = {
        "conversation_id": conversation_public_id,
        "last_message": last_message or {},
    }
    for uid in user_ids:
        broadcast_to_user(uid, "conversation_updated", payload)


def broadcast_notification(*, user_id: int, title: str, body: str, data: dict | None = None) -> None:
    broadcast_to_user(
        user_id,
        "notification",
        {
            "title": title,
            "body": body,
            "data": data or {},
        },
    )


def broadcast_subscription_update(*, user_id: int, is_premium: bool, expires_at: str | None) -> None:
    broadcast_to_user(
        user_id,
        "subscription_updated",
        {
            "is_premium": is_premium,
            "expires_at": expires_at,
        },
    )


def broadcast_compatibility_updated(*, match) -> None:
    score = int(getattr(match, "compatibility_score", 0) or 0)
    payload = {
        "match_id": match.id,
        "compatibility_score": score,
        "user1_id": match.user1_id,
        "user2_id": match.user2_id,
    }
    broadcast_to_user(match.user1_id, "compatibility_updated", payload)
    broadcast_to_user(match.user2_id, "compatibility_updated", payload)


def broadcast_profile_verified(*, user_id: int) -> None:
    broadcast_to_user(
        user_id,
        "profile_verified",
        {"verified": True},
    )
    from notifications.dispatch import dispatch_profile_verified_push

    dispatch_profile_verified_push(user_id=user_id)


def broadcast_presence(*, user_id: int, presence: dict) -> None:
    broadcast_to_user(user_id, "presence_update", presence)
