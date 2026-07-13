from __future__ import annotations

import secrets
import string
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


def _generate_public_id() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(12))


class CallSession(models.Model):
    TYPE_VOICE = "voice"
    TYPE_VIDEO = "video"
    TYPE_CHOICES = [
        (TYPE_VOICE, "Voice"),
        (TYPE_VIDEO, "Video"),
    ]

    STATUS_INITIATING = "initiating"
    STATUS_RINGING = "ringing"
    STATUS_ACTIVE = "active"
    STATUS_ENDED = "ended"
    STATUS_MISSED = "missed"
    STATUS_REJECTED = "rejected"
    STATUS_BUSY = "busy"
    STATUS_CANCELLED = "cancelled"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_INITIATING, "Initiating"),
        (STATUS_RINGING, "Ringing"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_ENDED, "Ended"),
        (STATUS_MISSED, "Missed"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_BUSY, "Busy"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_FAILED, "Failed"),
    ]

    public_id = models.CharField(max_length=16, unique=True, default=_generate_public_id, db_index=True)
    conversation = models.ForeignKey(
        "chat.Conversation",
        on_delete=models.CASCADE,
        related_name="calls",
    )
    caller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="calls_initiated",
    )
    callee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="calls_received",
    )
    call_type = models.CharField(max_length=8, choices=TYPE_CHOICES, default=TYPE_VOICE)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_INITIATING)
    end_reason = models.CharField(max_length=64, blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    ring_timeout_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    quality_summary = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["conversation", "-started_at"], name="call_convo_started_idx"),
            models.Index(fields=["caller", "status"], name="call_caller_status_idx"),
            models.Index(fields=["callee", "status"], name="call_callee_status_idx"),
            models.Index(fields=["status", "ring_timeout_at"], name="call_ring_timeout_idx"),
        ]

    def __str__(self) -> str:
        return f"Call {self.public_id} ({self.call_type}/{self.status})"

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            self.STATUS_ENDED,
            self.STATUS_MISSED,
            self.STATUS_REJECTED,
            self.STATUS_BUSY,
            self.STATUS_CANCELLED,
            self.STATUS_FAILED,
        }

    @property
    def is_ringing_expired(self) -> bool:
        if not self.ring_timeout_at:
            return False
        return timezone.now() >= self.ring_timeout_at

    def other_user_id(self, user_id: int) -> int:
        return self.callee_id if user_id == self.caller_id else self.caller_id

    def participant_ids(self) -> tuple[int, int]:
        return self.caller_id, self.callee_id
