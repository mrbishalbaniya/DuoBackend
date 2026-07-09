from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


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

        profile = getattr(message.sender, "profile", None)
        sender_name = (getattr(profile, "full_name", None) or "").strip() or message.sender.username
        if (message.content or "").strip():
            body = message.content.strip()
        elif message.image_url:
            body = "Sent a photo"
        else:
            body = "New message"

        frontend = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
        link = f"{frontend}/message?conversation={convo.id}"

        service.send_to_user(
            recipient.id,
            title=sender_name,
            body=body[:200],
            data={
                "type": "chat_message",
                "conversation_id": str(convo.id),
            },
            link=link,
        )
    except Exception:
        logger.exception("Failed to dispatch chat push notification")
