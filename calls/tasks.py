"""Celery tasks for call lifecycle."""

from __future__ import annotations

from celery import shared_task

from calls.services import timeout_ringing_call


@shared_task(name="calls.tasks.timeout_call_if_ringing")
def timeout_call_if_ringing(call_id: int) -> None:
    timeout_ringing_call(call_id)
