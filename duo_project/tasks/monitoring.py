"""Celery queue health and observability."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("duo.celery")


def get_celery_health() -> dict[str, Any]:
    """Return queue/worker metrics for admin dashboards and analytics."""
    enabled = bool(getattr(settings, "CELERY_ENABLED", False))
    eager = bool(getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False))
    result: dict[str, Any] = {
        "enabled": enabled,
        "eager_mode": eager,
        "broker_url_configured": bool(getattr(settings, "CELERY_BROKER_URL", "")),
        "result_backend": getattr(settings, "CELERY_RESULT_BACKEND", ""),
        "queues": ["default"],
        "workers_online": 0,
        "active_tasks": 0,
        "reserved_tasks": 0,
        "scheduled_tasks": 0,
        "recent_failures": 0,
        "recent_successes": 0,
        "slow_tasks": [],
        "status": "disabled",
    }

    if not enabled and eager:
        result["status"] = "eager"
        return result
    if not enabled:
        return result

    try:
        from duo_project.celery import app

        inspect = app.control.inspect(timeout=1.0)
        if inspect:
            active = inspect.active() or {}
            reserved = inspect.reserved() or {}
            scheduled = inspect.scheduled() or {}
            stats = inspect.stats() or {}

            result["workers_online"] = len(stats)
            result["active_tasks"] = sum(len(v) for v in active.values())
            result["reserved_tasks"] = sum(len(v) for v in reserved.values())
            result["scheduled_tasks"] = sum(len(v) for v in scheduled.values())
            result["status"] = "healthy" if stats else "no_workers"
    except Exception as exc:
        logger.debug("celery_inspect_failed: %s", exc)
        result["status"] = "unreachable"

    try:
        from django_celery_results.models import TaskResult

        since = timezone.now() - timedelta(hours=24)
        qs = TaskResult.objects.filter(date_done__gte=since)
        result["recent_failures"] = qs.filter(status="FAILURE").count()
        result["recent_successes"] = qs.filter(status="SUCCESS").count()
        slow = (
            qs.exclude(meta__isnull=True)
            .order_by("-date_done")[:20]
        )
        for row in slow:
            meta = row.meta if isinstance(row.meta, dict) else {}
            duration = meta.get("duration_ms")
            if duration and int(duration) > 5000:
                result["slow_tasks"].append(
                    {
                        "task": row.task_name,
                        "duration_ms": duration,
                        "task_id": row.task_id,
                    }
                )
    except Exception:
        pass

    return result
