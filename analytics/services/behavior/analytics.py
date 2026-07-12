"""Behavior analytics from event store."""

from __future__ import annotations

from django.db.models import Count

from analytics.models import AnalyticsEvent
from analytics.services.base import DateRange


def get_behavior_analytics(filters: dict | None = None) -> dict:
    filters = filters or {}
    date_range = DateRange.from_request(filters)
    start, end = date_range.as_datetimes()

    events = AnalyticsEvent.objects.filter(occurred_at__gte=start, occurred_at__lte=end)
    by_type = list(events.values("event_type").annotate(count=Count("id")).order_by("-count")[:30])
    by_category = list(events.values("category").annotate(count=Count("id")).order_by("-count"))
    by_platform = list(events.values("platform").annotate(count=Count("id")).order_by("-count"))

    return {
        "period": {"start": date_range.start.isoformat(), "end": date_range.end.isoformat()},
        "total_events": events.count(),
        "by_event_type": by_type,
        "by_category": by_category,
        "by_platform": by_platform,
        "top_features": [
            {"feature": r["event_type"], "usage": r["count"]} for r in by_type[:10]
        ],
    }
