"""System performance analytics."""

from __future__ import annotations

import os
import time

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone


def get_system_analytics() -> dict:
    db_latency = _measure_db_latency()
    cache_ok = _check_cache()
    redis_ok = _check_redis()

    return {
        "timestamp": timezone.now().isoformat(),
        "api": {
            "response_time_ms": db_latency,
            "status": "healthy" if db_latency < 500 else "slow",
        },
        "database": {
            "healthy": db_latency > 0,
            "latency_ms": db_latency,
            "engine": connection.vendor,
        },
        "cache": {
            "backend": settings.CACHES["default"]["BACKEND"].split(".")[-1],
            "healthy": cache_ok,
        },
        "redis": {
            "configured": bool(getattr(settings, "CHANNEL_LAYERS", {}).get("default", {}).get("CONFIG", {}).get("hosts")),
            "healthy": redis_ok,
        },
        "resources": _resource_metrics(),
        "background_jobs": {
            "celery": False,
            "queues": [],
        },
        "websocket": {
            "channels_enabled": "channels" in settings.INSTALLED_APPS,
            "backend": settings.CHANNEL_LAYERS.get("default", {}).get("BACKEND", ""),
        },
    }


def _measure_db_latency() -> float:
    try:
        start = time.perf_counter()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return round((time.perf_counter() - start) * 1000, 2)
    except Exception:
        return -1


def _check_cache() -> bool:
    try:
        cache.set("analytics_health", "ok", 10)
        return cache.get("analytics_health") == "ok"
    except Exception:
        return False

def _resource_metrics() -> dict:
    try:
        import psutil

        root = os.environ.get("SYSTEM_DRIVE", "C:\\") if os.name == "nt" else "/"
        disk = psutil.disk_usage(root)
        return {
            "cpu_pct": round(psutil.cpu_percent(interval=0.1), 1),
            "memory_pct": round(psutil.virtual_memory().percent, 1),
            "storage_usage_pct": round(disk.percent, 1),
        }
    except Exception:
        return {"cpu_pct": 0, "memory_pct": 0, "storage_usage_pct": 0}


def _check_redis() -> bool:
    try:
        import redis

        redis_url = os.environ.get("REDIS_URL", "").strip().strip('"').strip("'")
        if not redis_url:
            return False
        kwargs = {"socket_connect_timeout": 2}
        if redis_url.startswith("rediss://"):
            kwargs["ssl_cert_reqs"] = None
        client = redis.from_url(redis_url, **kwargs)
        return client.ping()
    except Exception:
        return False
