"""Portal dashboard data — composes analytics + portal-specific widgets."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.utils import timezone

from analytics.services.dashboard.realtime import get_realtime_metrics
from analytics.services.kpi.executive import get_executive_dashboard, get_revenue_timeseries
from analytics.services.base import DateRange
from analytics.services.maps.analytics import get_map_analytics
from analytics.services.matching.analytics import get_matching_analytics
from analytics.services.users.analytics import get_user_analytics
from chat.models import UserReport
from photo_verification.models import UserVerification
from subscriptions.models import Wallet

User = get_user_model()


def get_portal_dashboard(user=None) -> dict:
    executive = get_executive_dashboard()
    realtime = get_realtime_metrics()
    date_range = DateRange.from_request({"period": "30d"})
    revenue_ts = get_revenue_timeseries(date_range)
    users = get_user_analytics({"period": "30d"})
    matching = get_matching_analytics({"period": "30d"})
    maps = get_map_analytics()

    wallet_balance = Wallet.objects.aggregate(total=Sum("balance"))["total"] or 0
    pending_verifications = UserVerification.objects.filter(verification_status="PENDING").count()
    open_reports = UserReport.objects.count()

    return {
        "kpis": _flatten_kpis(executive, realtime, wallet_balance, pending_verifications, open_reports),
        "realtime": realtime,
        "charts": {
            "revenue": revenue_ts,
            "user_growth": users.get("growth", []),
            "matches": matching.get("distribution", {}).get("matches_by_day", []),
            "gender": users.get("segmentation", {}).get("gender", []),
            "platform": users.get("segmentation", {}).get("platform", []),
            "cities": maps.get("city_distribution", [])[:10],
        },
        "system": executive.get("system", {}),
        "role": _resolve_role(user),
    }


def _flatten_kpis(executive, realtime, wallet_balance, pending_verifications, open_reports):
    rev = executive.get("revenue", {})
    usr = executive.get("users", {})
    eng = executive.get("engagement", {})
    return {
        "total_users": usr.get("total", 0),
        "todays_users": usr.get("new_today", 0),
        "online_users": realtime.get("online_users", usr.get("online", 0)),
        "verified_users": usr.get("verified", 0),
        "premium_users": usr.get("premium", 0),
        "total_revenue": rev.get("yearly", 0),
        "todays_revenue": rev.get("today", 0),
        "monthly_revenue": rev.get("monthly", 0),
        "matches_today": realtime.get("new_matches", 0),
        "messages_today": realtime.get("new_messages", eng.get("total_messages", 0)),
        "active_conversations": eng.get("total_chats", 0),
        "wallet_balance": float(wallet_balance),
        "pending_verifications": pending_verifications,
        "open_reports": open_reports,
        "server_health": executive.get("system", {}).get("status", "unknown"),
        "api_status": "healthy" if executive.get("system", {}).get("database") else "degraded",
        "database_status": "up" if executive.get("system", {}).get("database") else "down",
        "redis_status": "configured",
        "storage_usage_pct": executive.get("system", {}).get("storage_usage_pct", 0),
    }


def _resolve_role(user) -> str:
    if not user or not user.is_authenticated:
        return "guest"
    if user.is_superuser:
        return "super_admin"
    if user.is_staff:
        return "admin"
    groups = set(user.groups.values_list("name", flat=True))
    if "analytics_finance" in groups:
        return "finance"
    if "analytics_support" in groups:
        return "support"
    if "analytics_marketing" in groups:
        return "marketing"
    return "admin"
