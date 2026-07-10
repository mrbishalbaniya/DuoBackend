"""Shared chat business logic for REST and WebSocket layers."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db.models import Max
from django.utils import timezone

from .models import Conversation, Message, MessageReaction, UserBlock


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
