"""Background metric aggregation into snapshots."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from analytics.models import DailyMetricSnapshot, FunnelSnapshot, HourlyMetricSnapshot
from analytics.services.dashboard.realtime import get_realtime_metrics
from analytics.services.funnel.analytics import get_funnel_analytics
from analytics.services.kpi.executive import get_executive_dashboard


def aggregate_hourly():
    now = timezone.now().replace(minute=0, second=0, microsecond=0)
    metrics = {
        "realtime": get_realtime_metrics(),
        "executive": get_executive_dashboard(),
    }
    HourlyMetricSnapshot.objects.update_or_create(
        bucket_start=now,
        defaults={"metrics": metrics},
    )
    return metrics


def aggregate_daily(target_date=None):
    target_date = target_date or timezone.localdate()
    filters = {
        "start_date": (target_date - timedelta(days=29)).isoformat(),
        "end_date": target_date.isoformat(),
    }
    metrics = {
        "executive": get_executive_dashboard(filters),
        "funnel": get_funnel_analytics(filters),
    }
    DailyMetricSnapshot.objects.update_or_create(
        date=target_date,
        defaults={"metrics": metrics},
    )
    funnel = metrics["funnel"]
    FunnelSnapshot.objects.update_or_create(
        date=target_date,
        funnel_name="onboarding",
        defaults={"stages": funnel.get("stages", {})},
    )
    return metrics
