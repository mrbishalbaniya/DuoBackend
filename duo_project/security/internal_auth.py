"""Shared-secret auth for service-to-service calls from chat-service.

Used by the internal endpoints chat-service calls (notifications/
internal_views.py, matching/internal_views.py) — never exposed to end users,
not part of the public API schema.
"""

from __future__ import annotations

from django.conf import settings
from rest_framework.permissions import BasePermission


class ChatServiceTokenPermission(BasePermission):
    """Authorize requests from chat-service via CHAT_INTERNAL_TOKEN."""

    def has_permission(self, request, view) -> bool:
        expected = getattr(settings, "CHAT_INTERNAL_TOKEN", "").strip()
        if not expected:
            return False
        header = request.headers.get("Authorization", "")
        provided = header[7:].strip() if header.lower().startswith("bearer ") else ""
        return provided == expected
