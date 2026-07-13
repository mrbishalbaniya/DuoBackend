"""Celery tasks for push notifications."""

from __future__ import annotations

import logging

from celery import shared_task

from duo_project.tasks import NETWORK_RETRY_KWARGS
from notifications import workers

logger = logging.getLogger("duo.celery")


@shared_task(name="notifications.tasks.send_chat_message_push", **NETWORK_RETRY_KWARGS)
def send_chat_message_push_task(message_id: int) -> None:
    workers.execute_chat_message_push(message_id)


@shared_task(name="notifications.tasks.send_message_reaction_push", **NETWORK_RETRY_KWARGS)
def send_message_reaction_push_task(message_id: int, reactor_id: int, emoji: str) -> None:
    workers.execute_message_reaction_push(message_id, reactor_id, emoji)


@shared_task(name="notifications.tasks.send_like_push", **NETWORK_RETRY_KWARGS)
def send_like_push_task(from_user_id: int, to_user_id: int, action: str) -> None:
    workers.execute_like_push(from_user_id, to_user_id, action)


@shared_task(name="notifications.tasks.send_match_push", **NETWORK_RETRY_KWARGS)
def send_match_push_task(match_id: int) -> None:
    workers.execute_match_push(match_id)


@shared_task(name="notifications.tasks.send_profile_viewed_push", **NETWORK_RETRY_KWARGS)
def send_profile_viewed_push_task(viewer_id: int, viewed_user_id: int) -> None:
    workers.execute_profile_viewed_push(viewer_id, viewed_user_id)


@shared_task(name="notifications.tasks.send_profile_verified_push", **NETWORK_RETRY_KWARGS)
def send_profile_verified_push_task(user_id: int) -> None:
    workers.execute_profile_verified_push(user_id)


@shared_task(name="notifications.tasks.send_photo_approved_push", **NETWORK_RETRY_KWARGS)
def send_photo_approved_push_task(user_id: int) -> None:
    workers.execute_photo_approved_push(user_id)


@shared_task(name="notifications.tasks.send_subscription_purchased_push", **NETWORK_RETRY_KWARGS)
def send_subscription_purchased_push_task(user_id: int, plan_name: str = "Premium") -> None:
    workers.execute_subscription_purchased_push(user_id, plan_name)


@shared_task(name="notifications.tasks.send_payment_push", **NETWORK_RETRY_KWARGS)
def send_payment_push_task(user_id: int, success: bool, detail: str = "") -> None:
    workers.execute_payment_push(user_id, success, detail)


@shared_task(name="notifications.tasks.send_verification_update_push", **NETWORK_RETRY_KWARGS)
def send_verification_update_push_task(user_id: int, title: str, body: str) -> None:
    workers.execute_verification_update_push(user_id, title, body)


@shared_task(name="notifications.tasks.send_incoming_call_push", **NETWORK_RETRY_KWARGS)
def send_incoming_call_push_task(
    call_id: str,
    conversation_id: str,
    caller_id: int,
    callee_id: int,
    call_type: str,
    caller_name: str,
) -> None:
    workers.execute_incoming_call_push(
        call_id,
        conversation_id,
        caller_id,
        callee_id,
        call_type,
        caller_name,
    )


@shared_task(name="notifications.tasks.send_missed_call_push", **NETWORK_RETRY_KWARGS)
def send_missed_call_push_task(
    call_id: str,
    conversation_id: str,
    caller_id: int,
    callee_id: int,
    call_type: str,
    caller_name: str,
) -> None:
    workers.execute_missed_call_push(
        call_id,
        conversation_id,
        caller_id,
        callee_id,
        call_type,
        caller_name,
    )
