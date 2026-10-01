"""Send the admin-editable email templates when real things happen.

Every email here is driven by a model change, so it fires no matter which code
path caused it (API, eSewa callback, admin edit, management command):

| Event                    | Trigger                                           |
|--------------------------|---------------------------------------------------|
| Welcome email            | Profile.is_onboarded False -> True                |
| New match notification   | Match created (both people get one)               |
| Subscription confirmed   | SubscriptionPayment status -> complete            |
| Subscription failed      | SubscriptionPayment / WalletTopUp status -> failed|
| Generic transactional    | WalletTransaction created: coin top-up, gift card |
|                          | redeemed, balance adjustment (receipts)           |
| Account status change    | User.is_active changed, Profile.is_verified changed|
| Admin announcement       | Admin action "Send announcement email" (admin.py) |

Emails are sent after the database transaction commits and never raise, so a
mail problem can't break a payment, match or sign-up. Admins can switch any
event off under Email events, and edit every template under Email templates.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from email_service.constants import EmailEvent

logger = logging.getLogger(__name__)
User = get_user_model()


# ── helpers ────────────────────────────────────────────────────────────────
def _display_name(user) -> str:
    profile = getattr(user, "profile", None)
    name = (getattr(profile, "full_name", "") or "").strip()
    return name.split(" ")[0] if name else (user.username or "there")


def _money(value) -> str:
    amount = Decimal(value or 0)
    return f"NPR {amount:,.0f}"


def _coins(value) -> str:
    amount = Decimal(value or 0)
    return f"{abs(amount):,.0f} coins"


def _date(value) -> str:
    return value.strftime("%b %d, %Y") if value else ""


# Which per-user email preference controls each event. Events not listed
# here (OTP codes, password reset, login verification, email change,
# welcome) are essential and always sent.
EMAIL_PREFERENCE_BY_EVENT = {
    EmailEvent.MATCH_NOTIFICATION: "email_matches",
    EmailEvent.SUBSCRIPTION_CONFIRMED: "email_payments",
    EmailEvent.SUBSCRIPTION_FAILED: "email_payments",
    EmailEvent.GENERIC: "email_payments",
    EmailEvent.ACCOUNT_STATUS: "email_verification",
    EmailEvent.ADMIN_ANNOUNCEMENT: "email_announcements",
}


def user_wants_email(user, event: str, *, essential: bool = False) -> bool:
    """Respect the user's email preferences unless the email is essential."""
    field = EMAIL_PREFERENCE_BY_EVENT.get(event)
    if essential or not field:
        return True
    try:
        from notifications.models import NotificationPreference

        prefs = NotificationPreference.objects.filter(user=user).first()
    except Exception:  # pragma: no cover - never block mail on a lookup error
        logger.exception("Could not read email preferences for user %s", getattr(user, "pk", None))
        return True
    if prefs is None:
        return True
    return bool(prefs.email_enabled and getattr(prefs, field, True))


def send_user_email(user, event: str, context: dict | None = None, *, allow_inactive: bool = False) -> None:
    """Queue a templated email to a user after the current transaction commits.

    Account activation/deactivation notices (allow_inactive=True) are treated
    as essential and bypass the user's email preferences.
    """
    email = (getattr(user, "email", "") or "").strip()
    if not email or (not user.is_active and not allow_inactive):
        return
    if not user_wants_email(user, event, essential=allow_inactive):
        return
    ctx = {"user_name": _display_name(user), **(context or {})}
    if isinstance(ctx.get("cta_url"), str) and "{site}" in ctx["cta_url"]:
        from email_service.rendering import site_url

        ctx["cta_url"] = ctx["cta_url"].replace("{site}", site_url() or "")

    def _send():
        try:
            from email_service.service import send_email

            send_email(event=event, to=email, context=ctx, fail_silently=True, queue=True)
        except Exception:  # pragma: no cover - never break the caller
            logger.exception("Could not send %s email to user %s", event, user.pk)

    transaction.on_commit(_send)


def _remember_previous(instance, fields: tuple[str, ...]) -> None:
    """Stash the stored values so post_save can see what changed."""
    previous = {}
    if instance.pk:
        row = type(instance).objects.filter(pk=instance.pk).values(*fields).first()
        previous = row or {}
    instance._email_previous = previous


def _changed(instance, field: str):
    """(old, new) when ``field`` changed on an existing row, else None."""
    previous = getattr(instance, "_email_previous", None)
    if not previous or field not in previous:
        return None
    old, new = previous[field], getattr(instance, field)
    return (old, new) if old != new else None


# ── Welcome + verification badge (Profile) ─────────────────────────────────
from accounts.models import Profile  # noqa: E402


@receiver(pre_save, sender=Profile, dispatch_uid="email_profile_pre_save")
def _profile_pre_save(sender, instance, **kwargs):
    _remember_previous(instance, ("is_onboarded", "is_verified"))


@receiver(post_save, sender=Profile, dispatch_uid="email_profile_post_save")
def _profile_post_save(sender, instance, created, **kwargs):
    if created:
        return
    user = instance.user

    onboarded = _changed(instance, "is_onboarded")
    if onboarded and onboarded[1]:
        send_user_email(user, EmailEvent.WELCOME)

    verified = _changed(instance, "is_verified")
    if verified:
        if verified[1]:
            send_user_email(
                user,
                EmailEvent.ACCOUNT_STATUS,
                {
                    "title": "You're verified",
                    "intro": "Your profile now shows the verified badge, so people know you're really you.",
                    "cta_label": "View my profile",
                    "cta_url": "{site}/profile",
                },
            )
        else:
            send_user_email(
                user,
                EmailEvent.ACCOUNT_STATUS,
                {
                    "title": "Your verified badge was removed",
                    "intro": "Your profile photos changed, so your badge needs a fresh selfie check.",
                    "note": "It takes under a minute. Your matches and chats are not affected.",
                    "cta_label": "Verify again",
                    "cta_url": "{site}/verify",
                },
            )


def send_verified_email(user) -> None:
    """For code that sets is_verified with queryset.update() (no signals)."""
    send_user_email(
        user,
        EmailEvent.ACCOUNT_STATUS,
        {
            "title": "You're verified",
            "intro": "Your profile now shows the verified badge, so people know you're really you.",
            "cta_label": "View my profile",
            "cta_url": "{site}/profile",
        },
    )


# ── Account activated / deactivated (User) ─────────────────────────────────
@receiver(pre_save, sender=User, dispatch_uid="email_user_pre_save")
def _user_pre_save(sender, instance, **kwargs):
    _remember_previous(instance, ("is_active",))


@receiver(post_save, sender=User, dispatch_uid="email_user_post_save")
def _user_post_save(sender, instance, created, **kwargs):
    change = _changed(instance, "is_active") if not created else None
    if not change:
        return
    if change[1]:
        context = {
            "title": "Your account is active again",
            "intro": "Welcome back! You can sign in and pick up where you left off.",
            "cta_label": "Sign in",
            "cta_url": "{site}/login",
        }
    else:
        context = {
            "title": "Your account has been deactivated",
            "intro": "You can't sign in to your account right now.",
            "note": "If you think this is a mistake, contact support and we'll review it.",
            "cta_label": "Contact support",
            "cta_url": "{site}/help",
        }
    send_user_email(instance, EmailEvent.ACCOUNT_STATUS, context, allow_inactive=True)


# ── New match ──────────────────────────────────────────────────────────────
from matching.models import Match  # noqa: E402


@receiver(post_save, sender=Match, dispatch_uid="email_match_created")
def _match_created(sender, instance, created, **kwargs):
    if not created:
        return
    for me, other in ((instance.user1, instance.user2), (instance.user2, instance.user1)):
        other_name = _display_name(other)
        send_user_email(
            me,
            EmailEvent.MATCH_NOTIFICATION,
            {
                "match_name": other_name,
                "intro": f"You and {other_name} liked each other. Say hello while it's fresh.",
                "cta_label": f"Message {other_name}",
                "cta_url": "{site}/chat",
            },
        )


# ── Subscription payments ──────────────────────────────────────────────────
from subscriptions.models import SubscriptionPayment, WalletTopUp, WalletTransaction  # noqa: E402


def _plan_name(plan_id: str) -> str:
    try:
        from subscriptions.services import get_plan_by_id

        return get_plan_by_id(plan_id).get("name") or plan_id
    except Exception:
        return plan_id.replace("_", " ").title()


@receiver(pre_save, sender=SubscriptionPayment, dispatch_uid="email_payment_pre_save")
def _payment_pre_save(sender, instance, **kwargs):
    _remember_previous(instance, ("status",))


@receiver(post_save, sender=SubscriptionPayment, dispatch_uid="email_payment_post_save")
def _payment_post_save(sender, instance, created, **kwargs):
    change = _changed(instance, "status")
    new_status = change[1] if change else (instance.status if created else None)
    if new_status not in (SubscriptionPayment.STATUS_COMPLETE, SubscriptionPayment.STATUS_FAILED):
        return

    plan = _plan_name(instance.plan_id)
    paid_with_wallet = instance.payment_source == SubscriptionPayment.SOURCE_WALLET
    details = [
        {"label": "Plan", "value": plan},
        {
            "label": "Amount",
            "value": _coins(instance.total_amount) if paid_with_wallet else _money(instance.total_amount),
        },
        {"label": "Paid with", "value": "Wallet coins" if paid_with_wallet else "eSewa"},
    ]

    if new_status == SubscriptionPayment.STATUS_COMPLETE:
        if getattr(instance, "expires_at", None):
            details.append({"label": "Active until", "value": _date(instance.expires_at)})
        details.append({"label": "Reference", "value": instance.transaction_uuid})
        send_user_email(
            instance.user,
            EmailEvent.SUBSCRIPTION_CONFIRMED,
            {
                "plan_name": plan,
                "title": f"{plan} is active",
                "intro": "Thank you! Your payment went through and your perks are ready to use.",
                "details": details,
                "cta_label": "Open Duo",
                "cta_url": "{site}/match",
            },
        )
    else:
        send_user_email(
            instance.user,
            EmailEvent.SUBSCRIPTION_FAILED,
            {
                "title": "Your payment didn't go through",
                "intro": f"We couldn't complete your payment for {plan}. You haven't been charged.",
                "details": details,
                "cta_label": "Try again",
                "cta_url": "{site}/wallet",
            },
        )


# ── Coin recharge failed ───────────────────────────────────────────────────
@receiver(pre_save, sender=WalletTopUp, dispatch_uid="email_topup_pre_save")
def _topup_pre_save(sender, instance, **kwargs):
    _remember_previous(instance, ("status",))


@receiver(post_save, sender=WalletTopUp, dispatch_uid="email_topup_post_save")
def _topup_post_save(sender, instance, created, **kwargs):
    change = _changed(instance, "status")
    if not change or change[1] != WalletTopUp.STATUS_FAILED:
        return
    send_user_email(
        instance.user,
        EmailEvent.SUBSCRIPTION_FAILED,
        {
            "title": "Coin recharge failed",
            "intro": "Your eSewa payment didn't go through, so no coins were added. You haven't been charged.",
            "details": [
                {"label": "Coins", "value": _coins(instance.amount)},
                {"label": "Amount", "value": _money(instance.total_amount)},
                {"label": "Reference", "value": instance.transaction_uuid},
            ],
            "cta_label": "Try again",
            "cta_url": "{site}/wallet",
        },
    )


# ── Wallet receipts: top-up, gift card, adjustment ─────────────────────────
_RECEIPTS = {
    WalletTransaction.TYPE_TOP_UP: ("Coins added to your wallet", "Your recharge was successful."),
    WalletTransaction.TYPE_GIFT_REDEEM: ("Gift card redeemed", "Your gift card coins are now in your wallet."),
    WalletTransaction.TYPE_ADJUSTMENT: ("Your wallet balance was updated", "Our team adjusted your coin balance."),
}


@receiver(post_save, sender=WalletTransaction, dispatch_uid="email_wallet_receipt")
def _wallet_receipt(sender, instance, created, **kwargs):
    # Purchases are covered by the subscription confirmation email.
    if not created or instance.status != WalletTransaction.STATUS_COMPLETE:
        return
    receipt = _RECEIPTS.get(instance.type)
    if not receipt:
        return
    title, intro = receipt
    amount = Decimal(instance.amount or 0)
    details = [
        {"label": "Coins added" if amount >= 0 else "Coins removed", "value": _coins(amount)},
        {"label": "New balance", "value": _coins(instance.balance_after)},
    ]
    if instance.type == WalletTransaction.TYPE_TOP_UP and instance.total_amount:
        details.append({"label": "Paid", "value": _money(instance.total_amount)})
        details.append({"label": "Paid with", "value": "eSewa"})
    if instance.description and instance.type == WalletTransaction.TYPE_ADJUSTMENT:
        details.append({"label": "Note", "value": instance.description})
    if instance.reference_id:
        details.append({"label": "Reference", "value": instance.reference_id})
    details.append({"label": "Date", "value": _date(instance.created_at)})

    send_user_email(
        instance.wallet.user,
        EmailEvent.GENERIC,
        {
            "title": title,
            "intro": intro,
            "details": details,
            "note": "Keep this email as your receipt.",
            "cta_label": "View my wallet",
            "cta_url": "{site}/wallet",
        },
    )
