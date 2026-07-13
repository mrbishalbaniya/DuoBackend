"""Enqueue Celery tasks with thread fallback when the broker is unavailable."""

from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger("duo.celery")


def safe_delay(task: Any, *args, **kwargs) -> Any:
    """
    Dispatch a Celery task asynchronously.

    Falls back to a daemon thread when the broker rejects the message so API
    handlers never block and notifications still attempt delivery.
    """
    try:
        return task.delay(*args, **kwargs)
    except Exception:
        logger.exception("celery_enqueue_failed task=%s", getattr(task, "name", task))

        def _run() -> None:
            try:
                task.apply(args=args, kwargs=kwargs)
            except Exception:
                logger.exception("celery_fallback_thread_failed task=%s", getattr(task, "name", task))

        thread = threading.Thread(
            target=_run,
            daemon=True,
            name="duo-celery-fallback",
        )
        thread.start()
        return None
