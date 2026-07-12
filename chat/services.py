"""Shared chat business logic for REST and WebSocket layers."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db.models import Max
from django.utils import timezone

from .models import Conversation, ConversationPreference, Message, MessageReaction, UserBlock


SECURITY_EVENT_SCREENSHOT = "SCREENSHOT_TAKEN"
SECURITY_EVENT_RECORDING_STARTED = "SCREEN_RECORDING_STARTED"
SECURITY_EVENT_RECORDING_STOPPED = "SCREEN_RECORDING_STOPPED"

SECURITY_EVENT_CODES = frozenset({
    SECURITY_EVENT_SCREENSHOT,
    SECURITY_EVENT_RECORDING_STARTED,
    SECURITY_EVENT_RECORDING_STOPPED,
})

_SECURITY_EVENT_DEBOUNCE_SECONDS = 2


def users_are_blocked(user_a: User, user_b: User) -> bool:
    return UserBlock.objects.filter(
        blocker_id__in=(user_a.id, user_b.id),
        blocked_id__in=(user_a.id, user_b.id),
    ).exists()


def conversation_is_blocked(convo: Conversation, user: User) -> bool:
    other = convo.match.get_other_user(user)
    return users_are_blocked(user, other)


def build_reactions_summary(message: Message) -> dict[str, list[int]]:
    """Return emoji -> list of user ids (one entry per user per emoji)."""
    summary: dict[str, list[int]] = {}
    for reaction in message.reactions.select_related("user").all():
        summary.setdefault(reaction.emoji, []).append(reaction.user_id)
    return summary


def infer_message_type(content: str, image_url: str) -> str:
    url = (image_url or "").lower()
    if url and any(ext in url for ext in (".webm", ".ogg", ".mp3", ".wav", ".m4a", ".aac")):
        return "voice"
    if url:
        return "image"
    return "text"


def touch_conversation_activity(convo: Conversation, when=None) -> None:
    when = when or timezone.now()
    Conversation.objects.filter(pk=convo.pk).update(last_message_at=when)


def delete_message_for_user(
    message: Message,
    user: User,
    delete_type: str,
) -> bool:
    if delete_type == "for_everyone":
        if message.sender_id != user.id:
            return False
        message.is_deleted_for_everyone = True
        message.save(update_fields=["is_deleted_for_everyone"])
        return True

    message.deleted_by.add(user)
    return True


def react_to_message(message: Message, user: User, emoji: str) -> dict[str, list[int]]:
    existing = MessageReaction.objects.filter(message=message, user=user, emoji=emoji)
    if existing.exists():
        existing.delete()
    else:
        MessageReaction.objects.create(message=message, user=user, emoji=emoji)
    return build_reactions_summary(message)


def mark_messages_read(convo: Conversation, reader: User) -> list[int]:
    """Mark incoming messages as read; return ids that changed."""
    now = timezone.now()
    qs = (
        convo.messages.exclude(sender=reader)
        .filter(is_read=False)
        .only("id")
    )
    ids = list(qs.values_list("id", flat=True))
    if not ids:
        return []

    convo.messages.filter(id__in=ids).update(is_read=True, read_at=now)
    # Backfill delivered_at for messages that were never marked delivered.
    convo.messages.filter(id__in=ids, delivered_at__isnull=True).update(delivered_at=now)
    return ids


def mark_messages_delivered(convo: Conversation, recipient: User) -> list[int]:
    """Mark other user's messages as delivered when recipient connects/opens thread."""
    now = timezone.now()
    qs = (
        convo.messages.exclude(sender=recipient)
        .filter(delivered_at__isnull=True)
        .only("id")
    )
    ids = list(qs.values_list("id", flat=True))
    if not ids:
        return []
    convo.messages.filter(id__in=ids).update(delivered_at=now)
    return ids


def backfill_conversation_last_message_at() -> None:
    """Utility for migration backfill."""
    for convo in Conversation.objects.all():
        latest = convo.messages.aggregate(latest=Max("timestamp"))["latest"]
        if latest:
            convo.last_message_at = latest
            convo.save(update_fields=["last_message_at"])


def _actor_display_name(user: User) -> str:
    profile = getattr(user, "profile", None)
    name = (getattr(profile, "full_name", None) or "").strip()
    return name or user.username or "Someone"


def format_security_event_content(actor_name: str, event_code: str) -> str:
    if event_code == SECURITY_EVENT_SCREENSHOT:
        return f"📸 {actor_name} took a screenshot."
    if event_code == SECURITY_EVENT_RECORDING_STARTED:
        return f"🎥 {actor_name} started screen recording."
    if event_code == SECURITY_EVENT_RECORDING_STOPPED:
        return f"🎥 {actor_name} stopped screen recording."
    return f"{actor_name} triggered a security event."


def user_notify_screenshots_enabled(convo: Conversation, user: User) -> bool:
    pref = ConversationPreference.objects.filter(conversation=convo, user=user).first()
    if pref is None:
        return True
    return bool(pref.notify_screenshots)


def should_record_security_event(convo: Conversation, actor: User, event_code: str) -> bool:
    if event_code not in SECURITY_EVENT_CODES:
        return False
    if not user_notify_screenshots_enabled(convo, actor):
        return False

    last = (
        convo.messages.filter(
            sender=actor,
            message_type=Message.MESSAGE_TYPE_SYSTEM,
            event_code=event_code,
        )
        .order_by("-timestamp")
        .first()
    )
    if last and (timezone.now() - last.timestamp).total_seconds() < _SECURITY_EVENT_DEBOUNCE_SECONDS:
        return False
    return True


def create_security_system_message(
    convo: Conversation,
    actor: User,
    event_code: str,
) -> Message | None:
    if conversation_is_blocked(convo, actor):
        return None
    if not should_record_security_event(convo, actor, event_code):
        return None

    actor_name = _actor_display_name(actor)
    content = format_security_event_content(actor_name, event_code)
    msg = Message.objects.create(
        conversation=convo,
        sender=actor,
        content=content,
        message_type=Message.MESSAGE_TYPE_SYSTEM,
        event_code=event_code,
    )
    touch_conversation_activity(convo, msg.timestamp)

    from notifications.dispatch import dispatch_chat_message_push

    dispatch_chat_message_push(msg)
    return msg
