from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from calls.models import CallSession
from chat.models import Conversation
from chat.services import conversation_is_blocked
from duo_project.realtime.broadcast import broadcast_to_user
from duo_project.realtime.groups import call_room
from duo_project.runtime_config import get_integration_settings

logger = logging.getLogger("duo.calls")

User = get_user_model()

RING_TIMEOUT_SECONDS = 45
ACTIVE_CALL_STATUSES = {
    CallSession.STATUS_INITIATING,
    CallSession.STATUS_RINGING,
    CallSession.STATUS_ACTIVE,
}


def get_ice_servers() -> list[dict]:
    """Return STUN/TURN ICE server configuration for WebRTC clients."""
    cfg = get_integration_settings()
    servers: list[dict] = []

    stun_urls = list(cfg.webrtc_stun_urls) or [
        "stun:stun.l.google.com:19302",
        "stun:stun1.l.google.com:19302",
    ]
    for url in stun_urls:
        servers.append({"urls": url})

    turn_url = (cfg.webrtc_turn_url or "").strip()
    if not turn_url:
        return servers

    turn_username = (cfg.webrtc_turn_username or "").strip()
    turn_credential = (cfg.webrtc_turn_credential or "").strip()
    turn_secret = (cfg.webrtc_turn_secret or "").strip()

    if turn_secret:
        expiry = int(time.time()) + int(cfg.webrtc_turn_ttl or 86400)
        turn_username = str(expiry)
        turn_credential = base64.b64encode(
            hmac.new(turn_secret.encode("utf-8"), turn_username.encode("utf-8"), hashlib.sha1).digest()
        ).decode("utf-8")

    if turn_username and turn_credential:
        servers.append(
            {
                "urls": turn_url,
                "username": turn_username,
                "credential": turn_credential,
            }
        )
    else:
        servers.append({"urls": turn_url})

    return servers


def user_has_active_call(user_id: int, exclude_call_id: int | None = None) -> bool:
    qs = CallSession.objects.filter(status__in=ACTIVE_CALL_STATUSES).filter(
        models.Q(caller_id=user_id) | models.Q(callee_id=user_id)
    )
    if exclude_call_id:
        qs = qs.exclude(pk=exclude_call_id)
    return qs.exists()


def can_user_call(user, conversation: Conversation) -> tuple[bool, str]:
    match = conversation.match
    if user.id not in (match.user1_id, match.user2_id):
        return False, "Not a conversation participant."
    if conversation_is_blocked(conversation, user):
        return False, "Cannot call blocked users."
    other_id = match.user2_id if user.id == match.user1_id else match.user1_id
    if user_has_active_call(user.id):
        return False, "You are already in a call."
    if user_has_active_call(other_id):
        return False, "User is busy."
    return True, ""


def serialize_call(call: CallSession, *, viewer_id: int | None = None) -> dict:
    return {
        "id": call.public_id,
        "conversation_id": call.conversation.public_id,
        "call_type": call.call_type,
        "status": call.status,
        "caller_id": call.caller_id,
        "callee_id": call.callee_id,
        "is_outgoing": viewer_id == call.caller_id if viewer_id else None,
        "started_at": call.started_at.isoformat() if call.started_at else None,
        "answered_at": call.answered_at.isoformat() if call.answered_at else None,
        "ended_at": call.ended_at.isoformat() if call.ended_at else None,
        "duration_seconds": call.duration_seconds,
        "end_reason": call.end_reason,
    }


def _broadcast_call_event(call: CallSession, event_type: str, payload: dict | None = None) -> None:
    body = {
        "call_id": call.public_id,
        "conversation_id": call.conversation.public_id,
        "call_type": call.call_type,
        "status": call.status,
        "caller_id": call.caller_id,
        "callee_id": call.callee_id,
        **(payload or {}),
    }
    for uid in call.participant_ids():
        broadcast_to_user(uid, event_type, body)


def _schedule_ring_timeout(call: CallSession) -> None:
    try:
        from calls.tasks import timeout_call_if_ringing

        timeout_call_if_ringing.apply_async(args=[call.id], countdown=RING_TIMEOUT_SECONDS)
    except Exception:
        logger.exception("call_timeout_schedule_failed call_id=%s", call.public_id)


def initiate_call(*, user, conversation: Conversation, call_type: str) -> tuple[CallSession | None, str]:
    allowed, reason = can_user_call(user, conversation)
    if not allowed:
        return None, reason

    match = conversation.match
    callee_id = match.user2_id if user.id == match.user1_id else match.user1_id
    now = timezone.now()

    call = CallSession.objects.create(
        conversation=conversation,
        caller=user,
        callee_id=callee_id,
        call_type=call_type,
        status=CallSession.STATUS_RINGING,
        ring_timeout_at=now + timedelta(seconds=RING_TIMEOUT_SECONDS),
    )

    from duo_project.realtime.presence import mark_ringing

    mark_ringing(user.id)
    mark_ringing(callee_id)

    _broadcast_call_event(
        call,
        "call_incoming",
        {
            "caller_name": _display_name(user),
            "caller_photo": _photo_url(user),
        },
    )

    from notifications.dispatch import dispatch_incoming_call_push

    dispatch_incoming_call_push(
        call_id=call.public_id,
        conversation_id=conversation.public_id,
        caller_id=user.id,
        callee_id=callee_id,
        call_type=call_type,
        caller_name=_display_name(user),
    )

    _schedule_ring_timeout(call)
    return call, ""


def accept_call(*, user, call: CallSession) -> tuple[CallSession | None, str]:
    if call.is_terminal:
        return None, "Call has already ended."
    if call.is_ringing_expired:
        finalize_call(call, status=CallSession.STATUS_MISSED, end_reason="timeout")
        return None, "Call timed out."
    if user.id != call.callee_id:
        return None, "Only the callee can accept."
    if call.status != CallSession.STATUS_RINGING:
        return None, "Call is not ringing."

    call.status = CallSession.STATUS_ACTIVE
    call.answered_at = timezone.now()
    call.save(update_fields=["status", "answered_at"])

    from duo_project.realtime.presence import mark_in_call

    mark_in_call(call.caller_id)
    mark_in_call(call.callee_id)

    _broadcast_call_event(call, "call_accepted")
    return call, ""


def reject_call(*, user, call: CallSession, reason: str = "rejected") -> tuple[CallSession | None, str]:
    if call.is_terminal:
        return call, ""
    if user.id not in call.participant_ids():
        return None, "Not a call participant."
    if user.id != call.callee_id:
        return None, "Only the callee can reject."

    finalize_call(call, status=CallSession.STATUS_REJECTED, end_reason=reason)
    _broadcast_call_event(call, "call_rejected", {"reason": reason})
    return call, ""


def cancel_call(*, user, call: CallSession, reason: str = "cancelled") -> tuple[CallSession | None, str]:
    if call.is_terminal:
        return call, ""
    if user.id != call.caller_id:
        return None, "Only the caller can cancel."
    if call.status not in {CallSession.STATUS_RINGING, CallSession.STATUS_INITIATING}:
        return None, "Call cannot be cancelled."

    finalize_call(call, status=CallSession.STATUS_CANCELLED, end_reason=reason)
    _broadcast_call_event(call, "call_cancelled", {"reason": reason})
    return call, ""


def hangup_call(*, user, call: CallSession, reason: str = "hangup") -> tuple[CallSession | None, str]:
    if call.is_terminal:
        return call, ""
    if user.id not in call.participant_ids():
        return None, "Not a call participant."

    finalize_call(call, status=CallSession.STATUS_ENDED, end_reason=reason)
    _broadcast_call_event(call, "call_ended", {"reason": reason})
    return call, ""


def mark_busy(*, user, call: CallSession) -> tuple[CallSession | None, str]:
    if call.is_terminal:
        return call, ""
    if user.id != call.callee_id:
        return None, "Only the callee can mark busy."

    finalize_call(call, status=CallSession.STATUS_BUSY, end_reason="busy")
    _broadcast_call_event(call, "call_busy")
    return call, ""


def finalize_call(call: CallSession, *, status: str, end_reason: str) -> CallSession:
    now = timezone.now()
    call.status = status
    call.end_reason = end_reason
    call.ended_at = now
    if call.answered_at:
        call.duration_seconds = max(0, int((now - call.answered_at).total_seconds()))
    call.save(update_fields=["status", "end_reason", "ended_at", "duration_seconds"])

    from duo_project.realtime.presence import clear_call_presence

    clear_call_presence(call.caller_id)
    clear_call_presence(call.callee_id)

    if status == CallSession.STATUS_MISSED:
        from notifications.dispatch import dispatch_missed_call_push

        dispatch_missed_call_push(
            call_id=call.public_id,
            conversation_id=call.conversation.public_id,
            caller_id=call.caller_id,
            callee_id=call.callee_id,
            call_type=call.call_type,
            caller_name=_display_name(call.caller),
        )

    return call


def timeout_ringing_call(call_id: int) -> None:
    call = CallSession.objects.select_related("caller", "conversation").filter(pk=call_id).first()
    if not call or call.status != CallSession.STATUS_RINGING:
        return
    if not call.is_ringing_expired and call.ring_timeout_at and timezone.now() < call.ring_timeout_at:
        return
    finalize_call(call, status=CallSession.STATUS_MISSED, end_reason="timeout")
    _broadcast_call_event(call, "call_missed", {"reason": "timeout"})


def get_call_for_user(public_id: str, user) -> tuple[CallSession | None, str]:
    call = (
        CallSession.objects.select_related("conversation", "caller", "callee")
        .filter(public_id=public_id)
        .first()
    )
    if not call:
        return None, "Call not found."
    if user.id not in call.participant_ids():
        return None, "Not a call participant."
    return call, ""


def relay_signaling_event(
    *,
    call: CallSession,
    sender_id: int,
    event_type: str,
    payload: dict,
) -> None:
    """Relay WebRTC signaling to the other participant via inbox + call room."""
    if call.is_terminal and event_type not in {"call_reconnect"}:
        return
    if sender_id not in call.participant_ids():
        return

    other_id = call.other_user_id(sender_id)
    message = {
        "type": "call_signal",
        "event": event_type,
        "call_id": call.public_id,
        "conversation_id": call.conversation.public_id,
        "sender_id": sender_id,
        "payload": payload,
    }
    broadcast_to_user(other_id, "call_signal", message)

    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    layer = get_channel_layer()
    if layer:
        async_to_sync(layer.group_send)(
            call_room(call.conversation.public_id),
            {
                "type": "call.signal",
                "message": message,
            },
        )


def _display_name(user) -> str:
    profile = getattr(user, "profile", None)
    name = (getattr(profile, "full_name", None) or "").strip()
    return name or user.username or "Someone"


def _photo_url(user) -> str:
    profile = getattr(user, "profile", None)
    if not profile:
        return ""
    photo = (getattr(profile, "photo_url", None) or "").strip()
    if photo:
        return photo
    urls = getattr(profile, "photo_urls", None) or []
    if isinstance(urls, list):
        for item in urls:
            if isinstance(item, str) and item.strip():
                return item.strip()
    return ""
