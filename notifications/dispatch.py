from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def _frontend_url() -> str:
    return getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")


def _display_name(user) -> str:
    profile = getattr(user, "profile", None)
    name = (getattr(profile, "full_name", None) or "").strip()
    return name or user.username or "Someone"


def _photo_url(user) -> str:
    profile = getattr(user, "profile", None)
    if not profile:
        return ""
    photo = (getattr(profile, "photo_url", None) or "").strip()
    if photo:
        return photo
    urls = getattr(profile, "photo_urls", None) or []
    if isinstance(urls, list):
        for item in urls:
            if isinstance(item, str) and item.strip():
                return item.strip()
    return ""


def _icon_url() -> str:
    return f"{_frontend_url()}/icons/duo-notification-192.png"


def _badge_url() -> str:
    return f"{_frontend_url()}/icons/duo-badge-96.png"


def dispatch_chat_message_push(message) -> None:
    try:
        from notifications.services.fcm import FCMService

        service = FCMService()
        if not service.is_configured():
            return

        convo = message.conversation
        match = convo.match
        if message.sender_id == match.user1_id:
            recipient = match.user2
        else:
            recipient = match.user1

        if recipient.id == message.sender_id:
            return

        sender_name = _display_name(message.sender)
        if message.message_type == "system":
            body = (message.content or "").strip() or "Security event in chat"
        elif (message.content or "").strip():
            body = message.content.strip()
        elif message.image_url:
            body = "Sent you a photo"
        else:
            body = "Sent you a new message"

        link = f"{_frontend_url()}/chat?conversation={convo.public_id}"
        photo = _photo_url(message.sender)

        service.send_to_user(
            recipient.id,
            title=sender_name,
            body=body[:200],
            data={
                "type": "chat_message",
                "conversation_id": str(convo.public_id),
                "sender_id": str(message.sender_id),
                "url": f"/chat?conversation={convo.public_id}",
                "theme": "duo",
            },
            link=link,
            icon=photo or _icon_url(),
            image=photo,
            tag=f"chat-{convo.id}",
        )
    except Exception:
        logger.exception("Failed to dispatch chat push notification")


def dispatch_like_push(*, from_user, to_user, action: str) -> None:
    """Notify someone that they received a like / superlike (not yet a match).

    Keep copy anonymous — revealing the liker would bypass the Who Liked You paywall.
    """
    try:
        from notifications.services.fcm import FCMService

        service = FCMService()
        if not service.is_configured():
            return

        if from_user.id == to_user.id:
            return

        is_super = action == "SUPERLIKE"
        title = "Someone superliked you" if is_super else "Someone liked you"
        body = (
            "A special someone sent you a superlike. Open Duo to find out who."
            if is_super
            else "Someone liked your profile. Open Duo to see who it is."
        )
        link = f"{_frontend_url()}/discover?tab=likes-you"

        service.send_to_user(
            to_user.id,
            title=title,
            body=body,
            data={
                "type": "profile_like",
                "from_user_id": str(from_user.id),
                "action": action,
                "url": "/discover?tab=likes-you",
            },
            link=link,
            icon=_icon_url(),
            tag=f"like-{from_user.id}",
        )
    except Exception:
        logger.exception("Failed to dispatch like push notification")


def dispatch_match_push(*, match) -> None:
    """Notify both users about a new mutual match — copy matches the celebration screen."""
    try:
        from notifications.services.fcm import FCMService

        service = FCMService()
        if not service.is_configured():
            return

        user_a = match.user1
        user_b = match.user2
        score = int(getattr(match, "compatibility_score", 0) or 0)

        conversation = getattr(match, "conversation", None)
        chat_path = (
            f"/chat?conversation={conversation.public_id}"
            if conversation is not None
            else "/chat"
        )
        link = f"{_frontend_url()}{chat_path}"

        for recipient, other in ((user_a, user_b), (user_b, user_a)):
            other_name = _display_name(other)
            photo = _photo_url(other)
            if score > 0:
                body = (
                    f"You and {other_name} have expressed interest in each other. "
                    f"{score}% compatible — start chatting."
                )
            else:
                body = (
                    f"You and {other_name} have expressed interest in each other. "
                    "Start chatting on Duo."
                )

            service.send_to_user(
                recipient.id,
                title="It's a Match!",
                body=body,
                data={
                    "type": "new_match",
                    "match_id": str(match.id),
                    "other_user_id": str(other.id),
                    "other_name": other_name,
                    "compatibility_score": str(score),
                    "url": chat_path,
                    "theme": "duo",
                },
                link=link,
                # Brand pink icon; match photo as the large image (celebration vibe)
                icon=_icon_url(),
                image=photo,
                tag=f"match-{match.id}",
            )
    except Exception:
        logger.exception("Failed to dispatch match push notification")
