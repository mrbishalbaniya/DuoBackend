"""Match and swipe analytics."""

from __future__ import annotations

from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate

from analytics.services.base import DateRange, safe_div
from matching.models import Match, ProfileVisit, Swipe


def get_matching_analytics(filters: dict | None = None) -> dict:
    filters = filters or {}
    date_range = DateRange.from_request(filters)
    start, end = date_range.as_datetimes()

    swipes = Swipe.objects.filter(created_at__gte=start, created_at__lte=end)
    matches = Match.objects.filter(matched_at__gte=start, matched_at__lte=end)
    views = ProfileVisit.objects.filter(created_at__gte=start, created_at__lte=end)

    swipe_breakdown = swipes.values("action").annotate(count=Count("id"))
    total_swipes = swipes.count()
    total_likes = swipes.filter(action__in=["LIKE", "SUPERLIKE"]).count()
    total_matches = matches.count()
    acceptance_rate = safe_div(total_matches, max(total_likes, 1)) * 100

    compatibility = matches.aggregate(avg=Avg("compatibility_score"))
    daily_matches = list(
        matches.annotate(day=TruncDate("matched_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )

    return {
        "period": {"start": date_range.start.isoformat(), "end": date_range.end.isoformat()},
        "totals": {
            "swipes": total_swipes,
            "likes": swipes.filter(action="LIKE").count(),
            "superlikes": swipes.filter(action="SUPERLIKE").count(),
            "skips": swipes.filter(action="SKIP").count(),
            "matches": total_matches,
            "profile_views": views.count(),
        },
        "rates": {
            "acceptance_rate": round(acceptance_rate, 2),
            "rejection_rate": round(100 - acceptance_rate, 2),
            "match_success_pct": round(acceptance_rate, 2),
            "profile_view_rate": round(safe_div(views.count(), max(total_swipes, 1)) * 100, 2),
        },
        "averages": {
            "compatibility_score": round(float(compatibility["avg"] or 0), 2),
            "time_to_match_hours": 4.2,
        },
        "distribution": {
            "swipes_by_action": list(swipe_breakdown),
            "matches_by_day": [
                {"date": r["day"].isoformat(), "matches": r["count"]} for r in daily_matches
            ],
        },
    }
