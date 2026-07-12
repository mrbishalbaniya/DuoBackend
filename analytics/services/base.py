"""Shared analytics utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.core.cache import cache
from django.db.models import QuerySet
from django.utils import timezone

from analytics.constants import CACHE_TTL_MEDIUM, CACHE_TTL_SHORT


@dataclass
class DateRange:
    start: date
    end: date

    @classmethod
    def from_request(cls, params: dict) -> "DateRange":
        today = timezone.localdate()
        start_raw = params.get("start_date") or params.get("start")
        end_raw = params.get("end_date") or params.get("end")
        if start_raw and end_raw:
            return cls(start=date.fromisoformat(str(start_raw)), end=date.fromisoformat(str(end_raw)))
        period = params.get("period", "30d")
        if period == "7d":
            return cls(start=today - timedelta(days=6), end=today)
        if period == "90d":
            return cls(start=today - timedelta(days=89), end=today)
        if period == "365d":
            return cls(start=today - timedelta(days=364), end=today)
        if period == "ytd":
            return cls(start=date(today.year, 1, 1), end=today)
        if period == "mtd":
            return cls(start=date(today.year, today.month, 1), end=today)
        return cls(start=today - timedelta(days=29), end=today)

    def as_datetimes(self) -> tuple[datetime, datetime]:
        tz = timezone.get_current_timezone()
        start_dt = timezone.make_aware(datetime.combine(self.start, datetime.min.time()), tz)
        end_dt = timezone.make_aware(datetime.combine(self.end, datetime.max.time()), tz)
        return start_dt, end_dt


def pct_change(current: float | Decimal, previous: float | Decimal) -> float:
    current_f = float(current or 0)
    previous_f = float(previous or 0)
    if previous_f == 0:
        return 100.0 if current_f > 0 else 0.0
    return round(((current_f - previous_f) / previous_f) * 100, 2)


def safe_div(numerator: float | Decimal, denominator: float | Decimal) -> float:
    denom = float(denominator or 0)
    if denom == 0:
        return 0.0
    return round(float(numerator or 0) / denom, 4)


def cache_key(prefix: str, **parts: Any) -> str:
    bits = [prefix] + [f"{k}={v}" for k, v in sorted(parts.items())]
    return ":".join(bits)


def cached_result(key: str, builder, ttl: int = CACHE_TTL_MEDIUM):
    hit = cache.get(key)
    if hit is not None:
        return hit
    value = builder()
    cache.set(key, value, ttl)
    return value


def apply_profile_filters(qs: QuerySet, filters: dict, prefix: str = "") -> QuerySet:
    field = f"{prefix}__" if prefix else ""
    if filters.get("gender"):
        qs = qs.filter(**{f"{field}gender": filters["gender"]})
    if filters.get("verified") in ("true", "1", True):
        qs = qs.filter(**{f"{field}is_verified": True})
    if filters.get("premium") in ("true", "1", True):
        qs = qs.filter(**{f"{field}user__subscription_payments__status": "complete"})
    if filters.get("country"):
        qs = qs.filter(**{f"{field}location__icontains": filters["country"]})
    return qs.distinct()


def serialize_decimal(value) -> float:
    if value is None:
        return 0.0
    return float(value)
