"""Synchronous push notification workers (invoked by Celery tasks)."""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger("duo.notifications")


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


def _is_conversation_muted(recipient_id: int, conversation) -> bool:
    try:
        from chat.models import ConversationPreference

        pref = ConversationPreference.objects.filter(
            user_id=recipient_id,
            conversation=conversation,
        ).first()
        return bool(pref and pref.is_muted)
    except Exception:
        return False


def execute_chat_message_push(message_id: int) -> None:
    from chat.models import Message
    from notifications.services.notification_service import (
        default_icon_url,
        send_push_notification,
    )
    from notifications.constants import CHAT_MESSAGE

    message = (
        Message.objects.select_related(
            "sender__profile",
            "conversation__match__user1__profile",
            "conversation__match__user2__profile",
        )
        .filter(pk=message_id)
        .first()
    )
    if not message:
        return

    convo = message.conversation
    match = convo.match
    recipient = match.user2 if message.sender_id == match.user1_id else match.user1
    if recipient.id == message.sender_id:
        return
    if _is_conversation_muted(recipient.id, convo):
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

    send_push_notification(
        user_id=recipient.id,
        notification_type=CHAT_MESSAGE,
        title=sender_name,
        body=body[:200],
        data={
            "conversation_id": str(convo.public_id),
            "sender_id": str(message.sender_id),
            "url": f"/chat?conversation={convo.public_id}",
            "theme": "duo",
        },
        link=link,
        icon=photo or default_icon_url(),
        image=photo,
        tag=f"chat-{convo.id}",
        skip_if_online=True,
    )


def execute_message_reaction_push(message_id: int, reactor_id: int, emoji: str) -> None:
    from chat.models import Message
    from django.contrib.auth import get_user_model
    from notifications.constants import MESSAGE_REACTION
    from notifications.services.notification_service import default_icon_url, send_push_notification

    User = get_user_model()
    message = Message.objects.select_related("conversation").filter(pk=message_id).first()
    reactor = User.objects.filter(pk=reactor_id).select_related("profile").first()
    if not message or not reactor or message.sender_id == reactor.id:
        return
    if _is_conversation_muted(message.sender_id, message.conversation):
        return

    convo = message.conversation
    reactor_name = _display_name(reactor)
    body = f"{reactor_name} reacted {emoji} to your message"
    link = f"{_frontend_url()}/chat?conversation={convo.public_id}"

    send_push_notification(
        user_id=message.sender_id,
        notification_type=MESSAGE_REACTION,
        title="New reaction",
        body=body[:200],
        data={
            "conversation_id": str(convo.public_id),
            "message_id": str(message.id),
            "emoji": emoji,
            "reactor_id": str(reactor.id),
            "url": f"/chat?conversation={convo.public_id}",
        },
        link=link,
        icon=_photo_url(reactor) or default_icon_url(),
        tag=f"reaction-{message.id}",
    )


def execute_like_push(from_user_id: int, to_user_id: int, action: str) -> None:
    from django.contrib.auth import get_user_model
    from notifications.constants import PROFILE_LIKE, SUPER_LIKE
    from notifications.services.notification_service import default_icon_url, send_push_notification

    if from_user_id == to_user_id:
        return
    User = get_user_model()
    to_user = User.objects.filter(pk=to_user_id).first()
    if not to_user:
        return

    is_super = action == "SUPERLIKE"
    notif_type = SUPER_LIKE if is_super else PROFILE_LIKE
    title = "Someone superliked you" if is_super else "Someone liked you"
    body = (
        "A special someone sent you a superlike. Open Duo to find out who."
        if is_super
        else "Someone liked your profile. Open Duo to see who it is."
    )
    link = f"{_frontend_url()}/discover?tab=likes-you"

    send_push_notification(
        user_id=to_user.id,
        notification_type=notif_type,
        title=title,
        body=body,
        data={
            "from_user_id": str(from_user_id),
            "action": action,
            "url": "/discover?tab=likes-you",
        },
        link=link,
        icon=default_icon_url(),
        tag=f"like-{from_user_id}",
    )


def execute_match_push(match_id: int) -> None:
    from matching.models import Match
    from notifications.constants import NEW_MATCH
    from notifications.services.notification_service import default_icon_url, send_push_notification

    match = (
        Match.objects.select_related(
            "user1__profile",
            "user2__profile",
            "conversation",
        )
        .filter(pk=match_id)
        .first()
    )
    if not match:
        return

    score = int(match.compatibility_score or 0)
    conversation = getattr(match, "conversation", None)
    chat_path = (
        f"/chat?conversation={conversation.public_id}" if conversation else "/chat"
    )
    link = f"{_frontend_url()}{chat_path}"

    for recipient, other in ((match.user1, match.user2), (match.user2, match.user1)):
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

        send_push_notification(
            user_id=recipient.id,
            notification_type=NEW_MATCH,
            title="It's a Match!",
            body=body,
            data={
                "match_id": str(match.id),
                "other_user_id": str(other.id),
                "other_name": other_name,
                "compatibility_score": str(score),
                "url": chat_path,
                "theme": "duo",
                "conversation_id": str(conversation.public_id) if conversation else "",
            },
            link=link,
            icon=default_icon_url(),
            image=photo,
            tag=f"match-{match.id}",
        )


def execute_profile_viewed_push(viewer_id: int, viewed_user_id: int) -> None:
    from notifications.constants import PROFILE_VIEWED
    from notifications.services.notification_service import default_icon_url, send_push_notification

    send_push_notification(
        user_id=viewed_user_id,
        notification_type=PROFILE_VIEWED,
        title="Someone viewed your profile",
        body="Open Duo to see who visited you.",
        data={"viewer_id": str(viewer_id), "url": "/discover?tab=visited-you"},
        link=f"{_frontend_url()}/discover?tab=visited-you",
        icon=default_icon_url(),
        tag=f"view-{viewer_id}",
    )


def execute_profile_verified_push(user_id: int) -> None:
    from notifications.constants import PROFILE_VERIFIED
    from notifications.services.notification_service import default_icon_url, send_push_notification

    send_push_notification(
        user_id=user_id,
        notification_type=PROFILE_VERIFIED,
        title="Profile verified",
        body="Your profile has been verified. You now have the verified badge.",
        data={"url": "/profile", "verified": "true"},
        link=f"{_frontend_url()}/profile",
        icon=default_icon_url(),
        tag="profile-verified",
    )


def execute_photo_approved_push(user_id: int) -> None:
    from notifications.constants import PHOTO_APPROVED
    from notifications.services.notification_service import default_icon_url, send_push_notification

    send_push_notification(
        user_id=user_id,
        notification_type=PHOTO_APPROVED,
        title="Photo approved",
        body="Your photo passed verification and is now live on your profile.",
        data={"url": "/profile"},
        link=f"{_frontend_url()}/profile",
        icon=default_icon_url(),
        tag="photo-approved",
    )


def execute_subscription_purchased_push(user_id: int, plan_name: str = "Premium") -> None:
    from notifications.constants import SUBSCRIPTION_PURCHASED
    from notifications.services.notification_service import default_icon_url, send_push_notification

    send_push_notification(
        user_id=user_id,
        notification_type=SUBSCRIPTION_PURCHASED,
        title="Welcome to Duo Premium",
        body=f"Your {plan_name} subscription is active. Enjoy premium features!",
        data={"url": "/settings"},
        link=f"{_frontend_url()}/settings",
        icon=default_icon_url(),
        tag="subscription-active",
    )


def execute_payment_push(user_id: int, success: bool, detail: str = "") -> None:
    from notifications.constants import PAYMENT_FAILURE, PAYMENT_SUCCESS
    from notifications.services.notification_service import default_icon_url, send_push_notification

    if success:
        send_push_notification(
            user_id=user_id,
            notification_type=PAYMENT_SUCCESS,
            title="Payment successful",
            body=detail or "Your payment was processed successfully.",
            data={"url": "/wallet"},
            link=f"{_frontend_url()}/wallet",
            icon=default_icon_url(),
            tag="payment-success",
        )
    else:
        send_push_notification(
            user_id=user_id,
            notification_type=PAYMENT_FAILURE,
            title="Payment failed",
            body=detail or "We could not process your payment. Please try again.",
            data={"url": "/wallet"},
            link=f"{_frontend_url()}/wallet",
            icon=default_icon_url(),
            tag="payment-failed",
        )


def execute_verification_update_push(user_id: int, title: str, body: str) -> None:
    from notifications.constants import VERIFICATION_UPDATE
    from notifications.services.notification_service import default_icon_url, send_push_notification

    send_push_notification(
        user_id=user_id,
        notification_type=VERIFICATION_UPDATE,
        title=title,
        body=body,
        data={"url": "/verify"},
        link=f"{_frontend_url()}/verify",
        icon=default_icon_url(),
        tag="verification-update",
    )


def execute_incoming_call_push(
    call_id: str,
    conversation_id: str,
    caller_id: int,
    callee_id: int,
    call_type: str,
    caller_name: str,
) -> None:
    from notifications.constants import CALL_INCOMING
    from notifications.services.notification_service import default_icon_url, send_push_notification

    label = "Video call" if call_type == "video" else "Voice call"
    link = f"{_frontend_url()}/chat?conversation={conversation_id}&call={call_id}&call_type={call_type}"
    send_push_notification(
        user_id=callee_id,
        notification_type=CALL_INCOMING,
        title=f"Incoming {label}",
        body=f"{caller_name} is calling you",
        data={
            "call_id": call_id,
            "conversation_id": conversation_id,
            "caller_id": str(caller_id),
            "call_type": call_type,
            "url": f"/chat?conversation={conversation_id}&call={call_id}&call_type={call_type}",
            "action": "incoming_call",
        },
        link=link,
        icon=default_icon_url(),
        tag=f"call-{call_id}",
        skip_if_online=False,
    )


def execute_missed_call_push(
    call_id: str,
    conversation_id: str,
    caller_id: int,
    callee_id: int,
    call_type: str,
    caller_name: str,
) -> None:
    from notifications.constants import CALL_MISSED
    from notifications.services.notification_service import default_icon_url, send_push_notification

    label = "video call" if call_type == "video" else "voice call"
    send_push_notification(
        user_id=callee_id,
        notification_type=CALL_MISSED,
        title="Missed call",
        body=f"Missed {label} from {caller_name}",
        data={
            "call_id": call_id,
            "conversation_id": conversation_id,
            "caller_id": str(caller_id),
            "call_type": call_type,
            "url": f"/chat?conversation={conversation_id}",
        },
        link=f"{_frontend_url()}/chat?conversation={conversation_id}",
        icon=default_icon_url(),
        tag=f"missed-call-{call_id}",
    )
