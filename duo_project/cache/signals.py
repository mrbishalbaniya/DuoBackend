"""Cache invalidation signal handlers."""

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import Profile
from chat.models import ConversationPreference, Message
from matching.models import Match, ProfileVisit, Swipe
from security.models import SecurityEvent
from photo_verification.constants import VerificationStatus
from photo_verification.models import UserVerification
from subscriptions.models import SubscriptionPayment, SubscriptionPlan, Wallet, WalletTopUp

from duo_project.cache.invalidation import (
    invalidate_conversation_for_users,
    invalidate_match_users,
    invalidate_profile_caches,
    invalidate_subscription_plans,
    invalidate_user_caches,
)

logger = logging.getLogger("duo.cache")
User = get_user_model()


@receiver(post_save, sender=Profile)
def profile_cache_invalidate(sender, instance, **kwargs):
    invalidate_profile_caches(instance.id, instance.user_id, reason="profile_save")


@receiver(post_save, sender=User)
def user_cache_invalidate(sender, instance, **kwargs):
    invalidate_user_caches(instance.id, reason="user_save")


@receiver(post_save, sender=Swipe)
def swipe_cache_invalidate(sender, instance, **kwargs):
    invalidate_user_caches(instance.from_user_id, reason="swipe")
    invalidate_user_caches(instance.to_user_id, reason="swipe")


@receiver(post_save, sender=Match)
def match_cache_invalidate(sender, instance, created, **kwargs):
    invalidate_match_users(instance.user1_id, instance.user2_id, reason="match")


@receiver(post_save, sender=ProfileVisit)
def visit_cache_invalidate(sender, instance, **kwargs):
    invalidate_user_caches(instance.viewed_user_id, reason="profile_visit")


@receiver(post_save, sender=Message)
def message_cache_invalidate(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        match = instance.conversation.match
        invalidate_conversation_for_users(
            instance.conversation_id,
            [match.user1_id, match.user2_id],
            reason="message",
        )
    except Exception:
        invalidate_user_caches(instance.sender_id, reason="message")


@receiver(post_save, sender=ConversationPreference)
def conversation_pref_cache_invalidate(sender, instance, **kwargs):
    invalidate_user_caches(instance.user_id, reason="conversation_pref")


@receiver(post_save, sender=SubscriptionPayment)
def subscription_cache_invalidate(sender, instance, **kwargs):
    invalidate_user_caches(instance.user_id, reason="subscription")
    if instance.status == SubscriptionPayment.STATUS_COMPLETE:
        invalidate_user_caches(instance.user_id, reason="subscription_active")


@receiver(post_save, sender=WalletTopUp)
def wallet_topup_cache_invalidate(sender, instance, **kwargs):
    if instance.status == WalletTopUp.STATUS_COMPLETE:
        invalidate_user_caches(instance.user_id, reason="wallet_topup")


@receiver(post_save, sender=Wallet)
def wallet_cache_invalidate(sender, instance, **kwargs):
    invalidate_user_caches(instance.user_id, reason="wallet")


@receiver(post_save, sender=SubscriptionPlan)
def subscription_plan_cache_invalidate(sender, instance, **kwargs):
    invalidate_subscription_plans()


@receiver(post_save, sender=SecurityEvent)
def security_event_cache_invalidate(sender, instance, **kwargs):
    invalidate_user_caches(instance.user_id, reason="security_event")


@receiver(post_save, sender=UserVerification)
def verification_cache_invalidate(sender, instance, **kwargs):
    if instance.verification_status == VerificationStatus.VERIFIED.value:
        invalidate_user_caches(instance.user_id, reason="verification")


def connect_cache_signals() -> None:
    """Imported for side effects from AppConfig.ready()."""
    logger.debug("cache_invalidation_signals_connected")
