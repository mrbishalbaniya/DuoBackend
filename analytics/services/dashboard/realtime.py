"""Real-time metrics snapshot for live dashboards."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone

from analytics.services.base import cache_key, cached_result
from analytics.services.kpi.executive import _revenue_between
from chat.models import Message, UserReport
from matching.models import Match
from photo_verification.models import UserVerification
from security.models import UserSession
from subscriptions.models import SubscriptionPayment

User = get_user_model()


def get_realtime_metrics() -> dict:
    return cached_result(
        cache_key("realtime_metrics"),
        _build_realtime_metrics,
        ttl=15,
    )


def _build_realtime_metrics() -> dict:
    now = timezone.now()
    today_start = timezone.make_aware(
        timezone.datetime.combine(timezone.localdate(), timezone.datetime.min.time()),
        timezone.get_current_timezone(),
    )
    online_cutoff = now - timedelta(minutes=5)
    last_hour = now - timedelta(hours=1)

    return {
        "timestamp": now.isoformat(),
        "online_users": UserSession.objects.filter(
            is_active=True, last_active__gte=online_cutoff
        ).values("user_id").distinct().count(),
        "new_registrations": User.objects.filter(date_joined__gte=last_hour).count(),
        "new_messages": Message.objects.filter(timestamp__gte=last_hour).count(),
        "new_matches": Match.objects.filter(matched_at__gte=last_hour).count(),
        "revenue_today": float(_revenue_between(today_start, now)),
        "failed_payments": SubscriptionPayment.objects.filter(
            status=SubscriptionPayment.STATUS_FAILED,
            created_at__gte=last_hour,
        ).count(),
        "support_requests": UserReport.objects.filter(created_at__gte=last_hour).count(),
        "verification_queue": UserVerification.objects.filter(verification_status="PENDING").count(),
        "server_load": {
            "websocket_connections": 0,
            "queue_depth": 0,
        },
    }
