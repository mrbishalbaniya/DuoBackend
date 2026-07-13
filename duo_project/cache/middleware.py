"""Lightweight middleware for cache-backed presence tracking."""

from __future__ import annotations

from django.conf import settings

from duo_project.cache.presence import mark_online


class CachePresenceMiddleware:
    """Mark authenticated users as online in Redis (30s TTL)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not getattr(settings, "CACHE_ENABLED", True):
            return response
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            try:
                mark_online(user.id)
            except Exception:
                pass
        return response
