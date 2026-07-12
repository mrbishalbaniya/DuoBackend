"""Retention and cohort analysis."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone

from analytics.models import CohortSnapshot
from analytics.services.base import DateRange, safe_div
from security.models import UserSession

User = get_user_model()

COHORT_PERIODS = [1, 7, 30, 90, 180, 365]


def get_retention_analytics(filters: dict | None = None) -> dict:
    filters = filters or {}
    date_range = DateRange.from_request(filters)
    now = timezone.now()

    inactive_cutoff = now - timedelta(days=30)
    lost_cutoff = now - timedelta(days=90)

    total = User.objects.filter(is_active=True).count()
    returning = User.objects.filter(last_login__gte=now - timedelta(days=7)).count()
    inactive = User.objects.filter(last_login__lt=inactive_cutoff, last_login__gte=lost_cutoff).count()
    lost = User.objects.filter(last_login__lt=lost_cutoff).count()

    cohorts = compute_cohort_matrix(date_range)

    return {
        "period": {"start": date_range.start.isoformat(), "end": date_range.end.isoformat()},
        "summary": {
            "returning_users": returning,
            "inactive_users": inactive,
            "lost_users": lost,
            "retention_rate_7d": round(safe_div(returning, total) * 100, 2),
            "churn_rate": round(safe_div(lost, total) * 100, 2),
        },
        "cohorts": cohorts,
    }


def compute_cohort_matrix(date_range: DateRange) -> list[dict]:
    from django.contrib.auth import get_user_model
    from django.db.models.functions import TruncDate

    User = get_user_model()
    start, end = date_range.as_datetimes()

    cohort_rows = (
        User.objects.filter(date_joined__gte=start, date_joined__lte=end)
        .annotate(cohort_date=TruncDate("date_joined"))
        .values("cohort_date")
        .annotate(cohort_size=Count("id"))
        .order_by("cohort_date")
    )

    matrix = []
    for row in cohort_rows[:12]:
        cohort_date = row["cohort_date"]
        size = row["cohort_size"]
        periods = {}
        for days in COHORT_PERIODS:
            window_start = cohort_date + timedelta(days=max(days - 1, 0))
            window_end = cohort_date + timedelta(days=days + 1)
            retained = UserSession.objects.filter(
                user__date_joined__date=cohort_date,
                last_active__date__gte=window_start,
                last_active__date__lte=window_end,
            ).values("user_id").distinct().count()
            rate = round(safe_div(retained, size) * 100, 2)
            periods[f"day_{days}"] = {"retained": retained, "rate": rate}
            CohortSnapshot.objects.update_or_create(
                cohort_date=cohort_date,
                period_days=days,
                defaults={"cohort_size": size, "retained_users": retained, "retention_rate": rate},
            )
        matrix.append({"cohort_date": str(cohort_date), "size": size, "periods": periods})
    return matrix
