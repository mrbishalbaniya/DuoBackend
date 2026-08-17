"""Celery tasks that push shadow-data updates to chat-service."""

from __future__ import annotations

from celery import shared_task

from duo_project import chat_service_client
from duo_project.tasks import NETWORK_RETRY_KWARGS


@shared_task(name="duo_project.tasks.sync_user_to_chat_service", **NETWORK_RETRY_KWARGS)
def sync_user_task(user_id: int) -> None:
    chat_service_client.sync_user(user_id)


@shared_task(name="duo_project.tasks.sync_match_to_chat_service", **NETWORK_RETRY_KWARGS)
def sync_match_task(match_id: int) -> None:
    chat_service_client.sync_match(match_id)


@shared_task(name="duo_project.tasks.delete_match_from_chat_service", **NETWORK_RETRY_KWARGS)
def delete_match_task(match_id: int) -> None:
    chat_service_client.delete_match(match_id)
