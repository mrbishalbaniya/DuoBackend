"""Event tracking and real-time broadcast."""

from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

from analytics.constants import REALTIME_GROUP
from analytics.models import AnalyticsEvent


def track_event(
    *,
    category: str,
    event_type: str,
    user=None,
    properties: dict | None = None,
    value=None,
    platform: str = "",
    country: str = "",
    city: str = "",
    device_id: str = "",
    session_id: str = "",
    occurred_at=None,
    broadcast: bool = True,
) -> AnalyticsEvent:
    event = AnalyticsEvent.objects.create(
        category=category,
        event_type=event_type,
        user=user,
        properties=properties or {},
        value=value,
        platform=platform,
        country=country,
        city=city,
        device_id=device_id,
        session_id=session_id,
        occurred_at=occurred_at or timezone.now(),
    )
    if broadcast:
        broadcast_realtime_event(event_type, properties or {})
    return event


def broadcast_realtime_event(event_type: str, payload: dict):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        REALTIME_GROUP,
        {
            "type": "analytics.event",
            "event_type": event_type,
            "payload": payload,
        },
    )


def broadcast_realtime_metrics(metrics: dict):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        REALTIME_GROUP,
        {
            "type": "analytics.metrics",
            "metrics": metrics,
        },
    )
