"""Portal notifications and activity timeline."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.admin.models import LogEntry
from django.utils import timezone

from analytics.models import AnalyticsEvent
from chat.models import UserReport
from photo_verification.models import UserVerification
from subscriptions.models import SubscriptionPayment


def get_notifications(limit: int = 20) -> list[dict]:
    items = []
    for v in UserVerification.objects.filter(verification_status="PENDING").order_by("-id")[:5]:
        items.append({
            "id": f"verify-{v.pk}",
            "type": "warning",
            "title": "Pending verification",
            "body": f"User {v.user_id} awaiting review",
            "url": f"/admin/photo_verification/userverification/{v.pk}/change/",
            "time": timezone.now().isoformat(),
            "read": False,
        })
    for p in SubscriptionPayment.objects.filter(status="failed").order_by("-created_at")[:5]:
        items.append({
            "id": f"pay-{p.pk}",
            "type": "error",
            "title": "Payment failed",
            "body": p.transaction_uuid,
            "url": f"/admin/subscriptions/subscriptionpayment/{p.pk}/change/",
            "time": p.created_at.isoformat(),
            "read": False,
        })
    for r in UserReport.objects.order_by("-created_at")[:5]:
        items.append({
            "id": f"report-{r.pk}",
            "type": "info",
            "title": "User report",
            "body": (r.reason or "Report submitted")[:80],
            "url": f"/admin/chat/userreport/{r.pk}/change/",
            "time": r.created_at.isoformat(),
            "read": False,
        })
    return items[:limit]


def get_recent_activity(limit: int = 15) -> list[dict]:
    activities = []
    for event in AnalyticsEvent.objects.order_by("-occurred_at")[:limit]:
        activities.append({
            "id": event.pk,
            "type": event.event_type,
            "category": event.category,
            "title": _event_title(event.event_type),
            "user_id": event.user_id,
            "time": event.occurred_at.isoformat(),
            "status": "success" if event.category != "security" else "warning",
        })
    if len(activities) < limit:
        for entry in LogEntry.objects.select_related("content_type", "user").order_by("-action_time")[:limit]:
            activities.append({
                "id": f"log-{entry.pk}",
                "type": entry.action_flag,
                "category": "admin",
                "title": str(entry),
                "user_id": entry.user_id,
                "time": entry.action_time.isoformat(),
                "status": "info",
            })
    return activities[:limit]


def get_menu_badges() -> dict:
    return {
        "verification": UserVerification.objects.filter(verification_status="PENDING").count(),
        "payments": SubscriptionPayment.objects.filter(status="failed").count(),
        "reports": UserReport.objects.count(),
        "security": AnalyticsEvent.objects.filter(category="security", occurred_at__gte=timezone.now() - timedelta(days=1)).count(),
    }


def _event_title(event_type: str) -> str:
    mapping = {
        "user_registered": "User registered",
        "match_created": "New match",
        "message_text": "Message sent",
        "subscription_activated": "Premium purchased",
        "wallet_topup": "Wallet recharge",
        "payment_failed": "Payment failed",
        "user_reported": "Support ticket",
    }
    return mapping.get(event_type, event_type.replace("_", " ").title())
