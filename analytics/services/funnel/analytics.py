"""Funnel analytics — onboarding to premium conversion."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, OuterRef
from django.utils import timezone

from accounts.models import Profile
from analytics.services.base import DateRange, safe_div
from chat.models import Message
from matching.models import Match, Swipe
from photo_verification.models import UserVerification
from subscriptions.models import SubscriptionPayment

User = get_user_model()


def get_funnel_analytics(filters: dict | None = None) -> dict:
    filters = filters or {}
    date_range = DateRange.from_request(filters)
    start, end = date_range.as_datetimes()

    users = User.objects.filter(date_joined__gte=start, date_joined__lte=end)
    total = users.count()

    registered = total
    verified = users.filter(
        Exists(UserVerification.objects.filter(user_id=OuterRef("pk"), verification_status="VERIFIED"))
    ).count()
    profile_complete = users.filter(
        Exists(Profile.objects.filter(user_id=OuterRef("pk"), is_onboarded=True))
    ).count()
    first_swipe = users.filter(Exists(Swipe.objects.filter(from_user_id=OuterRef("pk")))).count()
    first_match = users.filter(
        Exists(Match.objects.filter(user1_id=OuterRef("pk"))) | Exists(Match.objects.filter(user2_id=OuterRef("pk")))
    ).count()
    first_chat = users.filter(Exists(Message.objects.filter(sender_id=OuterRef("pk")))).count()
    premium = users.filter(
        Exists(SubscriptionPayment.objects.filter(user_id=OuterRef("pk"), status=SubscriptionPayment.STATUS_COMPLETE))
    ).count()
    renewal_user_ids = (
        SubscriptionPayment.objects.filter(status=SubscriptionPayment.STATUS_COMPLETE)
        .values("user_id")
        .annotate(payment_count=Count("id"))
        .filter(payment_count__gte=2)
        .values_list("user_id", flat=True)
    )
    renewal = users.filter(id__in=renewal_user_ids).count()

    stages = [
        {"stage": "visitor", "count": registered, "rate": 100.0, "drop_off": 0.0},
        {"stage": "registration", "count": registered, "rate": 100.0, "drop_off": 0.0},
        {"stage": "verification", "count": verified, "rate": round(safe_div(verified, registered) * 100, 2), "drop_off": round(100 - safe_div(verified, registered) * 100, 2)},
        {"stage": "profile_completion", "count": profile_complete, "rate": round(safe_div(profile_complete, registered) * 100, 2), "drop_off": round(safe_div(registered - profile_complete, registered) * 100, 2)},
        {"stage": "first_swipe", "count": first_swipe, "rate": round(safe_div(first_swipe, registered) * 100, 2), "drop_off": round(safe_div(profile_complete - first_swipe, max(profile_complete, 1)) * 100, 2)},
        {"stage": "first_match", "count": first_match, "rate": round(safe_div(first_match, registered) * 100, 2), "drop_off": round(safe_div(first_swipe - first_match, max(first_swipe, 1)) * 100, 2)},
        {"stage": "first_chat", "count": first_chat, "rate": round(safe_div(first_chat, registered) * 100, 2), "drop_off": round(safe_div(first_match - first_chat, max(first_match, 1)) * 100, 2)},
        {"stage": "premium_purchase", "count": premium, "rate": round(safe_div(premium, registered) * 100, 2), "drop_off": round(safe_div(first_chat - premium, max(first_chat, 1)) * 100, 2)},
        {"stage": "subscription_renewal", "count": renewal, "rate": round(safe_div(renewal, max(premium, 1)) * 100, 2), "drop_off": round(safe_div(premium - renewal, max(premium, 1)) * 100, 2)},
    ]

    return {
        "funnel": "onboarding",
        "period": {"start": date_range.start.isoformat(), "end": date_range.end.isoformat()},
        "total_entered": registered,
        "stages": stages,
        "overall_conversion": round(safe_div(premium, registered) * 100, 2),
        "generated_at": timezone.now().isoformat(),
    }
