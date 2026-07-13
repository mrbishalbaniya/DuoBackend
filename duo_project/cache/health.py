"""Health endpoint extension for cache metrics."""

from __future__ import annotations

from django.conf import settings

from duo_project.cache.service import api_cache


def cache_health() -> dict:
    backend = settings.CACHES.get("default", {}).get("BACKEND", "")
    redis_configured = bool(getattr(settings, "REDIS_URL", ""))
    stats = api_cache.get_stats()
    hits = stats.get("hit", 0)
    misses = stats.get("miss", 0)
    total = hits + misses
    hit_rate = round((hits / total) * 100, 2) if total else 0.0
    return {
        "backend": backend.rsplit(".", 1)[-1],
        "redis_configured": redis_configured,
        "hits": hits,
        "misses": misses,
        "errors": stats.get("error", 0),
        "invalidations": stats.get("invalidate", 0),
        "hit_rate_pct": hit_rate,
    }
