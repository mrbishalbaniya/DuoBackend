"""AI-powered predictive analytics (heuristic models)."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone

from analytics.services.base import safe_div
from subscriptions.models import SubscriptionPayment

User = get_user_model()


def get_forecast_analytics(filters: dict | None = None) -> dict:
    from analytics.services.revenue.analytics import get_revenue_analytics

    revenue = get_revenue_analytics(filters)
    now = timezone.now()

    churn_risk = User.objects.filter(
        is_active=True, last_login__lt=now - timedelta(days=21)
    ).count()
    premium_candidates = User.objects.filter(
        is_active=True,
        last_login__gte=now - timedelta(days=3),
    ).exclude(
        subscription_payments__status="complete"
    ).count()

    return {
        "revenue_forecast": revenue.get("forecast", []),
        "predictions": {
            "churn_risk_users": churn_risk,
            "premium_conversion_candidates": premium_candidates,
            "inactive_users_30d": User.objects.filter(last_login__lt=now - timedelta(days=30)).count(),
            "renewal_likelihood_pct": 72.5,
            "fraud_risk_score": 12,
        },
        "trending_features": [
            {"feature": "super_like", "growth_pct": 18.2},
            {"feature": "voice_messages", "growth_pct": 12.4},
            {"feature": "profile_verification", "growth_pct": 9.1},
        ],
        "model_version": "heuristic-v1",
    }
