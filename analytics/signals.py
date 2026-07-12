"""Analytics event tracking via Django signals."""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from analytics.services.events import track_event
from chat.models import Message, UserReport
from matching.models import Match, Swipe
from subscriptions.models import SubscriptionPayment, WalletTopUp

User = get_user_model()


@receiver(post_save, sender=User)
def on_user_registered(sender, instance, created, **kwargs):
    if created:
        track_event(
            category="user",
            event_type="user_registered",
            user=instance,
            properties={"username": instance.username},
        )


@receiver(post_save, sender=Swipe)
def on_swipe(sender, instance, created, **kwargs):
    if created:
        track_event(
            category="matching",
            event_type=f"swipe_{instance.action.lower()}",
            user=instance.from_user,
            properties={"to_user_id": instance.to_user_id, "action": instance.action},
        )


@receiver(post_save, sender=Match)
def on_match(sender, instance, created, **kwargs):
    if created:
        track_event(
            category="matching",
            event_type="match_created",
            user=instance.user1,
            properties={
                "match_id": instance.id,
                "compatibility_score": instance.compatibility_score,
            },
        )


@receiver(post_save, sender=Message)
def on_message(sender, instance, created, **kwargs):
    if created:
        track_event(
            category="chat",
            event_type=f"message_{instance.message_type}",
            user=instance.sender,
            properties={
                "conversation_id": instance.conversation_id,
                "message_type": instance.message_type,
            },
        )


@receiver(post_save, sender=SubscriptionPayment)
def on_subscription_payment(sender, instance, **kwargs):
    if instance.status == SubscriptionPayment.STATUS_COMPLETE:
        track_event(
            category="revenue",
            event_type="subscription_activated",
            user=instance.user,
            value=instance.total_amount,
            properties={"plan_id": instance.plan_id, "source": instance.payment_source},
        )
    elif instance.status == SubscriptionPayment.STATUS_FAILED:
        track_event(
            category="revenue",
            event_type="payment_failed",
            user=instance.user,
            properties={"plan_id": instance.plan_id},
        )


@receiver(post_save, sender=WalletTopUp)
def on_wallet_topup(sender, instance, **kwargs):
    if instance.status == WalletTopUp.STATUS_COMPLETE:
        track_event(
            category="revenue",
            event_type="wallet_topup",
            user=instance.user,
            value=instance.total_amount,
        )


@receiver(post_save, sender=UserReport)
def on_user_report(sender, instance, created, **kwargs):
    if created:
        track_event(
            category="security",
            event_type="user_reported",
            user=instance.reporter,
            properties={"reported_user_id": instance.reported_id},
        )
