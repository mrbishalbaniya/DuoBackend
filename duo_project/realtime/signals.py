"""Connect real-time broadcasts to Django signals."""

from __future__ import annotations

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from chat.models import Message
from matching.models import Match, ProfileVisit, Swipe
from subscriptions.models import SubscriptionPayment

from duo_project.realtime.broadcast import (
    broadcast_activity_refresh,
    broadcast_compatibility_updated,
    broadcast_conversation_updated,
    broadcast_like_event,
    broadcast_match_event,
    broadcast_profile_viewed,
    broadcast_subscription_update,
)

logger = logging.getLogger("duo.realtime")

_match_score_before: dict[int, int] = {}


@receiver(pre_save, sender=Match)
def _cache_match_score(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old = Match.objects.filter(pk=instance.pk).values_list("compatibility_score", flat=True).first()
        if old is not None:
            _match_score_before[instance.pk] = int(old)
    except Exception:
        pass


@receiver(post_save, sender=Swipe)
def on_swipe_realtime(sender, instance, created, **kwargs):
    broadcast_activity_refresh()
    if created and instance.action in ("LIKE", "SUPERLIKE"):
        broadcast_like_event(
            from_user_id=instance.from_user_id,
            to_user_id=instance.to_user_id,
            action=instance.action,
        )


@receiver(post_save, sender=Match)
def on_match_realtime(sender, instance, created, **kwargs):
    broadcast_activity_refresh()
    if created:
        conversation_public_id = None
        try:
            conversation_public_id = instance.conversation.public_id
        except Exception:
            pass
        broadcast_match_event(match=instance, conversation_public_id=conversation_public_id)
        return

    old_score = _match_score_before.pop(instance.pk, None)
    if old_score is not None and old_score != int(instance.compatibility_score or 0):
        broadcast_compatibility_updated(match=instance)


@receiver(post_save, sender=ProfileVisit)
def on_visit_realtime(sender, instance, **kwargs):
    broadcast_activity_refresh()
    broadcast_profile_viewed(
        viewer_id=instance.viewer_id,
        viewed_user_id=instance.viewed_user_id,
    )
    from notifications.dispatch import dispatch_profile_viewed_push

    dispatch_profile_viewed_push(
        viewer_id=instance.viewer_id,
        viewed_user_id=instance.viewed_user_id,
    )


@receiver(post_save, sender=Message)
def on_message_realtime(sender, instance, created, **kwargs):
    broadcast_activity_refresh()
    if not created:
        return
    try:
        convo = instance.conversation
        match = convo.match
        last_message = {
            "id": instance.id,
            "content": instance.content,
            "sender_id": instance.sender_id,
            "timestamp": instance.timestamp.isoformat(),
            "message_type": instance.message_type,
        }
        broadcast_conversation_updated(
            user_ids=[match.user1_id, match.user2_id],
            conversation_public_id=convo.public_id,
            last_message=last_message,
        )
    except Exception:
        logger.debug("conversation_updated_broadcast_skipped message_id=%s", instance.id)


@receiver(post_save, sender=SubscriptionPayment)
def on_subscription_realtime(sender, instance, **kwargs):
    if instance.status != SubscriptionPayment.STATUS_COMPLETE:
        return
    expires = instance.expires_at.isoformat() if instance.expires_at else None
    broadcast_subscription_update(
        user_id=instance.user_id,
        is_premium=True,
        expires_at=expires,
    )
    from notifications.dispatch import dispatch_subscription_purchased_push

    dispatch_subscription_purchased_push(user_id=instance.user_id)


def connect_realtime_signals() -> None:
    logger.debug("realtime_signals_connected")
