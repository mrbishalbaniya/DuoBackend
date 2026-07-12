"""Revenue analytics and forecasting."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from analytics.services.base import DateRange, safe_div, serialize_decimal
from analytics.services.kpi.executive import _revenue_between, get_revenue_timeseries
from subscriptions.models import SubscriptionPayment, WalletTopUp, WalletTransaction


def get_revenue_analytics(filters: dict | None = None) -> dict:
    filters = filters or {}
    date_range = DateRange.from_request(filters)
    start, end = date_range.as_datetimes()

    subscription_rev = (
        SubscriptionPayment.objects.filter(
            status=SubscriptionPayment.STATUS_COMPLETE,
            paid_at__gte=start,
            paid_at__lte=end,
        ).aggregate(total=Sum("total_amount"), count=Count("id"))
    )
    wallet_rev = (
        WalletTopUp.objects.filter(
            status=WalletTopUp.STATUS_COMPLETE,
            paid_at__gte=start,
            paid_at__lte=end,
        ).aggregate(total=Sum("total_amount"), count=Count("id"))
    )
    refunds = SubscriptionPayment.objects.filter(
        status=SubscriptionPayment.STATUS_CANCELED,
        updated_at__gte=start,
        updated_at__lte=end,
    ).aggregate(total=Sum("total_amount"), count=Count("id"))

    gross = Decimal(subscription_rev["total"] or 0) + Decimal(wallet_rev["total"] or 0)
    net = gross - Decimal(refunds["total"] or 0)
    timeseries = get_revenue_timeseries(date_range)
    forecast = _simple_forecast(timeseries)

    by_plan = list(
        SubscriptionPayment.objects.filter(
            status="complete", paid_at__gte=start, paid_at__lte=end
        )
        .values("plan_id")
        .annotate(revenue=Sum("total_amount"), count=Count("id"))
        .order_by("-revenue")
    )

    return {
        "period": {"start": date_range.start.isoformat(), "end": date_range.end.isoformat()},
        "totals": {
            "gross_revenue": serialize_decimal(gross),
            "net_revenue": serialize_decimal(net),
            "subscriptions": serialize_decimal(subscription_rev["total"] or 0),
            "wallet_topups": serialize_decimal(wallet_rev["total"] or 0),
            "refunds": serialize_decimal(refunds["total"] or 0),
            "transactions": (subscription_rev["count"] or 0) + (wallet_rev["count"] or 0),
        },
        "by_plan": [
            {"plan_id": r["plan_id"], "revenue": serialize_decimal(r["revenue"]), "count": r["count"]}
            for r in by_plan
        ],
        "timeseries": timeseries,
        "forecast": forecast,
    }


def _simple_forecast(timeseries: list[dict], days: int = 14) -> list[dict]:
    if len(timeseries) < 2:
        return []
    recent = [r["total"] for r in timeseries[-7:]]
    avg = sum(recent) / len(recent)
    last_date = timeseries[-1]["date"]
    from datetime import date, timedelta

    base = date.fromisoformat(last_date)
    return [
        {"date": (base + timedelta(days=i + 1)).isoformat(), "predicted_revenue": round(avg, 2)}
        for i in range(days)
    ]
