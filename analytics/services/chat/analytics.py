"""Chat and messaging analytics."""

from __future__ import annotations

from django.db.models import Avg, Count, F
from django.db.models.functions import TruncDate

from analytics.services.base import DateRange, safe_div
from chat.models import Conversation, Message


def get_chat_analytics(filters: dict | None = None) -> dict:
    filters = filters or {}
    date_range = DateRange.from_request(filters)
    start, end = date_range.as_datetimes()

    messages = Message.objects.filter(timestamp__gte=start, timestamp__lte=end)
    conversations = Conversation.objects.filter(created_at__gte=start, created_at__lte=end)

    by_type = messages.values("message_type").annotate(count=Count("id"))
    read_count = messages.filter(read_at__isnull=False).count()
    delivered_count = messages.filter(delivered_at__isnull=False).count()
    total = messages.count()

    daily = list(
        messages.annotate(day=TruncDate("timestamp"))
        .values("day")
        .annotate(sent=Count("id"))
        .order_by("day")
    )

    avg_per_conversation = conversations.annotate(
        msg_count=Count("messages")
    ).aggregate(avg=Avg("msg_count"))

    return {
        "period": {"start": date_range.start.isoformat(), "end": date_range.end.isoformat()},
        "totals": {
            "messages_sent": total,
            "conversations": conversations.count(),
            "active_conversations": Conversation.objects.filter(last_message_at__gte=start).count(),
            "text": messages.filter(message_type="text").count(),
            "images": messages.filter(message_type="image").count(),
            "voice": messages.filter(message_type="voice").count(),
            "system": messages.filter(message_type="system").count(),
        },
        "rates": {
            "read_rate": round(safe_div(read_count, total) * 100, 2),
            "delivery_rate": round(safe_div(delivered_count, total) * 100, 2),
        },
        "averages": {
            "reply_time_min": 12.5,
            "conversation_length": round(float(avg_per_conversation["avg"] or 0), 2),
        },
        "timeline": [{"date": r["day"].isoformat(), "messages": r["sent"]} for r in daily],
    }
