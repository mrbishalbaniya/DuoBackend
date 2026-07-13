"""Email background tasks."""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from duo_project.tasks import NETWORK_RETRY_KWARGS

logger = logging.getLogger("duo.celery")


@shared_task(name="duo_project.tasks.email.send_email_task", **NETWORK_RETRY_KWARGS)
def send_email_task(
    *,
    event: str,
    to: str | list[str],
    subject: str | None = None,
    message: str | None = None,
    html_message: str | None = None,
    context: dict[str, Any] | None = None,
) -> bool:
    from email_service.service import send_email

    return send_email(
        event=event,
        to=to,
        subject=subject,
        message=message,
        html_message=html_message,
        context=context or {},
        fail_silently=False,
        queue=False,
    )


def queue_email(**kwargs) -> bool:
    """Enqueue email delivery; runs synchronously when Celery eager mode is on."""
    from django.conf import settings

    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        return send_email_task(**kwargs)
    send_email_task.delay(**kwargs)
    return True
