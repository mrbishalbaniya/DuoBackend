"""AI-powered predictive analytics (heuristic models)."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone

from analytics.services.base import safe_div
from analytics.services.security.analytics import get_fraud_signals
from subscriptions.models import SubscriptionPayment

User = get_user_model()


def get_forecast_analytics(filters: dict | None = None) -> dict:
    from analytics.models import AnalyticsEvent
    from analytics.services.revenue.analytics import get_revenue_analytics

    revenue = get_revenue_analytics(filters)
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    churn_risk = User.objects.filter(
        is_active=True, last_login__lt=now - timedelta(days=21)
    ).count()
    premium_candidates = User.objects.filter(
        is_active=True,
        last_login__gte=now - timedelta(days=3),
    ).exclude(
        subscription_payments__status=SubscriptionPayment.STATUS_COMPLETE
    ).count()

    recent_events = AnalyticsEvent.objects.filter(occurred_at__gte=week_ago).values("event_type").annotate(
        count=Count("id")
    )
    prior_events = {
        row["event_type"]: row["count"]
        for row in AnalyticsEvent.objects.filter(
            occurred_at__gte=two_weeks_ago, occurred_at__lt=week_ago
        ).values("event_type").annotate(count=Count("id"))
    }
    trending = []
    for row in recent_events:
        prior = prior_events.get(row["event_type"], 0)
        growth = round(((row["count"] - prior) / max(prior, 1)) * 100, 1) if prior else 100.0
        trending.append({"feature": row["event_type"], "growth_pct": growth})
    trending.sort(key=lambda item: item["growth_pct"], reverse=True)

    renewal_users = User.objects.filter(
        subscription_payments__status=SubscriptionPayment.STATUS_COMPLETE
    ).annotate(payment_count=Count("subscription_payments")).filter(payment_count__gte=2).count()
    premium_users = User.objects.filter(
        subscription_payments__status=SubscriptionPayment.STATUS_COMPLETE
    ).distinct().count()
    renewal_likelihood = round((renewal_users / max(premium_users, 1)) * 100, 1)

    fraud = get_fraud_signals(filters)

    return {
        "revenue_forecast": revenue.get("forecast", []),
        "predictions": {
            "churn_risk_users": churn_risk,
            "premium_conversion_candidates": premium_candidates,
            "inactive_users_30d": User.objects.filter(last_login__lt=now - timedelta(days=30)).count(),
            "renewal_likelihood_pct": renewal_likelihood,
            "fraud_risk_score": fraud.get("risk_score", 0),
        },
        "trending_features": trending[:6] or [
            {"feature": "super_like", "growth_pct": 0},
            {"feature": "voice_messages", "growth_pct": 0},
            {"feature": "profile_verification", "growth_pct": 0},
        ],
        "model_version": "heuristic-v2",
    }
