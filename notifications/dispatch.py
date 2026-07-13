from __future__ import annotations

import logging

from duo_project.tasks.enqueue import safe_delay
from notifications import tasks as notification_tasks

logger = logging.getLogger("duo.notifications")


def dispatch_chat_message_push(message) -> None:
    safe_delay(notification_tasks.send_chat_message_push_task, message.id)


def dispatch_message_reaction_push(*, message, reactor, emoji: str) -> None:
    safe_delay(
        notification_tasks.send_message_reaction_push_task,
        message.id,
        reactor.id,
        emoji,
    )


def dispatch_like_push(*, from_user, to_user, action: str) -> None:
    safe_delay(
        notification_tasks.send_like_push_task,
        from_user.id,
        to_user.id,
        action,
    )


def dispatch_match_push(*, match) -> None:
    safe_delay(notification_tasks.send_match_push_task, match.id)


def dispatch_profile_viewed_push(*, viewer_id: int, viewed_user_id: int) -> None:
    safe_delay(
        notification_tasks.send_profile_viewed_push_task,
        viewer_id,
        viewed_user_id,
    )


def dispatch_profile_verified_push(*, user_id: int) -> None:
    safe_delay(notification_tasks.send_profile_verified_push_task, user_id)


def dispatch_photo_approved_push(*, user_id: int) -> None:
    safe_delay(notification_tasks.send_photo_approved_push_task, user_id)


def dispatch_subscription_purchased_push(*, user_id: int, plan_name: str = "Premium") -> None:
    safe_delay(
        notification_tasks.send_subscription_purchased_push_task,
        user_id,
        plan_name,
    )


def dispatch_payment_push(*, user_id: int, success: bool, detail: str = "") -> None:
    safe_delay(
        notification_tasks.send_payment_push_task,
        user_id,
        success,
        detail,
    )


def dispatch_verification_update_push(*, user_id: int, title: str, body: str) -> None:
    safe_delay(
        notification_tasks.send_verification_update_push_task,
        user_id,
        title,
        body,
    )


def dispatch_incoming_call_push(
    *,
    call_id: str,
    conversation_id: str,
    caller_id: int,
    callee_id: int,
    call_type: str,
    caller_name: str,
) -> None:
    safe_delay(
        notification_tasks.send_incoming_call_push_task,
        call_id,
        conversation_id,
        caller_id,
        callee_id,
        call_type,
        caller_name,
    )


def dispatch_missed_call_push(
    *,
    call_id: str,
    conversation_id: str,
    caller_id: int,
    callee_id: int,
    call_type: str,
    caller_name: str,
) -> None:
    safe_delay(
        notification_tasks.send_missed_call_push_task,
        call_id,
        conversation_id,
        caller_id,
        callee_id,
        call_type,
        caller_name,
    )
