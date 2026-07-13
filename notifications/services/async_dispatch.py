"""Fire-and-forget notification dispatch without blocking HTTP handlers."""

from __future__ import annotations

import logging
import threading
from typing import Callable

logger = logging.getLogger("duo.notifications")


def enqueue_notification(task: Callable[[], None]) -> None:
    """
    Run notification work on a background daemon thread.

    Prefer Celery via ``duo_project.tasks.enqueue.safe_delay`` in dispatch.py.
    This helper remains for legacy call sites and Celery broker fallbacks.
    """
    def _run() -> None:
        try:
            task()
        except Exception:
            logger.exception("background_notification_task_failed")

    thread = threading.Thread(target=_run, daemon=True, name="duo-push")
    thread.start()
