"""Rate throttles that degrade gracefully when Redis/cache is unavailable."""

from __future__ import annotations

import logging

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

logger = logging.getLogger("duo.throttle")


class FailOpenMixin:
    """Allow requests when the throttle backend cannot be reached."""

    def allow_request(self, request, view):
        try:
            return super().allow_request(request, view)
        except Exception as exc:
            logger.warning(
                "throttle_cache_failed scope=%s path=%s error=%s",
                getattr(self, "scope", ""),
                getattr(request, "path", ""),
                exc,
            )
            return True


class FailOpenAnonRateThrottle(FailOpenMixin, AnonRateThrottle):
    pass


class FailOpenUserRateThrottle(FailOpenMixin, UserRateThrottle):
    pass
