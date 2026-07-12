"""Geographic and map analytics."""

from __future__ import annotations

from collections import Counter

from accounts.models import Profile
from analytics.services.base import DateRange
from activity.services.zones import compute_activity_zones


def get_map_analytics(filters: dict | None = None) -> dict:
    filters = filters or {}
    locations = (
        Profile.objects.exclude(location="")
        .exclude(location__isnull=True)
        .values_list("location", flat=True)[:5000]
    )
    counter = Counter(locations)
    top_locations = [{"location": loc, "count": cnt} for loc, cnt in counter.most_common(50)]

    zones = compute_activity_zones(
        lat_min=-90, lat_max=90, lon_min=-180, lon_max=180, zoom=2, user=None
    )

    return {
        "heatmap_zones": zones[:100],
        "popular_locations": top_locations,
        "country_distribution": _aggregate_by_country(top_locations),
        "city_distribution": top_locations[:20],
        "total_with_location": len(locations),
    }


def _aggregate_by_country(locations: list[dict]) -> list[dict]:
    countries: dict[str, int] = {}
    for item in locations:
        loc = item["location"]
        country = loc.split(",")[-1].strip() if "," in loc else loc
        countries[country] = countries.get(country, 0) + item["count"]
    return [{"country": k, "count": v} for k, v in sorted(countries.items(), key=lambda x: -x[1])]
