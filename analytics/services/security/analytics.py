"""Security and fraud analytics."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone

from analytics.services.base import DateRange
from chat.models import UserReport
from security.models import LoginHistory, SecurityEvent, UserDevice

User = get_user_model()


def get_security_analytics(filters: dict | None = None) -> dict:
    filters = filters or {}
    date_range = DateRange.from_request(filters)
    start, end = date_range.as_datetimes()

    failed_logins = LoginHistory.objects.filter(
        success=False, created_at__gte=start, created_at__lte=end
    ).count()
    security_events = SecurityEvent.objects.filter(created_at__gte=start, created_at__lte=end)
    by_type = list(security_events.values("event_type").annotate(count=Count("id")).order_by("-count"))
    reports = UserReport.objects.filter(created_at__gte=start, created_at__lte=end).count()
    multi_device = (
        UserDevice.objects.values("user_id")
        .annotate(device_count=Count("id"))
        .filter(device_count__gt=3)
        .count()
    )

    return {
        "period": {"start": date_range.start.isoformat(), "end": date_range.end.isoformat()},
        "totals": {
            "failed_logins": failed_logins,
            "security_events": security_events.count(),
            "user_reports": reports,
            "multi_device_users": multi_device,
            "blocked_users": User.objects.filter(is_active=False).count(),
        },
        "events_by_type": by_type,
        "suspicious_activity": security_events.filter(
            event_type__in=["suspicious_login", "failed_login"]
        ).count(),
        "generated_at": timezone.now().isoformat(),
    }


def get_fraud_signals(filters: dict | None = None) -> dict:
    filters = filters or {}
    date_range = DateRange.from_request(filters)
    start, end = date_range.as_datetimes()

    rapid_swipes = 0
    fake_profiles = UserReport.objects.filter(
        created_at__gte=start, created_at__lte=end, reason__icontains="fake"
    ).count()
    bot_signals = SecurityEvent.objects.filter(
        event_type="suspicious_login", created_at__gte=start, created_at__lte=end
    ).count()

    return {
        "period": {"start": date_range.start.isoformat(), "end": date_range.end.isoformat()},
        "signals": {
            "fake_profile_reports": fake_profiles,
            "bot_detection_hits": bot_signals,
            "rapid_swipe_accounts": rapid_swipes,
            "vpn_usage": 0,
        },
        "risk_score": min(100, fake_profiles * 5 + bot_signals * 3),
    }
