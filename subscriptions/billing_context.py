"""Batch subscription and wallet lookups for list serializers."""

from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from .models import SubscriptionPayment, Wallet
from .wallet_services import get_or_create_wallet


def build_profile_billing_context(user_ids: list[int] | set[int]) -> dict[int, dict]:
    """
    Batch-load premium status, expiry, and wallet balance for many profiles.

    Returns {user_id: {"is_premium": bool, "subscription_expires_at": datetime|None, "wallet_balance": int}}
    """
    if not user_ids:
        return {}

    unique_ids = {int(uid) for uid in user_ids if uid}
    now = timezone.now()
    context: dict[int, dict] = {
        uid: {
            "is_premium": False,
            "subscription_expires_at": None,
            "wallet_balance": 0,
        }
        for uid in unique_ids
    }

    active_payments = (
        SubscriptionPayment.objects.filter(
            user_id__in=unique_ids,
            status=SubscriptionPayment.STATUS_COMPLETE,
            expires_at__gt=now,
        )
        .order_by("user_id", "-expires_at")
        .values("user_id", "expires_at")
    )
    seen_users: set[int] = set()
    for row in active_payments:
        uid = row["user_id"]
        if uid in seen_users:
            continue
        seen_users.add(uid)
        context[uid]["is_premium"] = True
        context[uid]["subscription_expires_at"] = row["expires_at"]

    wallet_rows = Wallet.objects.filter(user_id__in=unique_ids).values("user_id", "balance")
    for row in wallet_rows:
        context[row["user_id"]]["wallet_balance"] = int(row["balance"] or Decimal("0"))

    return context


def ensure_viewer_wallet_in_context(context: dict[int, dict], user) -> dict[int, dict]:
    """Ensure the requesting user's wallet exists when only their profile is serialized."""
    if not user or not getattr(user, "is_authenticated", False):
        return context
    if user.id in context:
        return context
    wallet = get_or_create_wallet(user)
    context[user.id] = {
        "is_premium": False,
        "subscription_expires_at": None,
        "wallet_balance": int(wallet.balance),
    }
    active = (
        SubscriptionPayment.objects.filter(
            user=user,
            status=SubscriptionPayment.STATUS_COMPLETE,
            expires_at__gt=timezone.now(),
        )
        .order_by("-expires_at")
        .values("expires_at")
        .first()
    )
    if active:
        context[user.id]["is_premium"] = True
        context[user.id]["subscription_expires_at"] = active["expires_at"]
    return context
