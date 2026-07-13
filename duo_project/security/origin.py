"""Origin validation for cookie-authenticated API mutations (CSRF defense-in-depth)."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from django.conf import settings
from django.http import JsonResponse

logger = logging.getLogger("duo.security")

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _trusted_origins() -> set[str]:
    origins: set[str] = set()
    for origin in getattr(settings, "CORS_ALLOWED_ORIGINS", []) or []:
        origins.add(origin.rstrip("/"))
    frontend = getattr(settings, "FRONTEND_URL", "").rstrip("/")
    if frontend:
        origins.add(frontend)
    for host in getattr(settings, "ALLOWED_HOSTS", []) or []:
        if host and host not in ("localhost", "127.0.0.1", "*"):
            origins.add(f"https://{host}")
            origins.add(f"http://{host}")
    return origins


def _origin_from_referer(referer: str) -> str:
    if not referer:
        return ""
    parsed = urlparse(referer)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


class CookieOriginMiddleware:
    """
    Reject cross-site mutations that include the httpOnly auth cookie without
    a trusted Origin/Referer. Bearer-token clients (Flutter) are unaffected.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._trusted = _trusted_origins()

    def __call__(self, request):
        if (
            not settings.DEBUG
            and request.method in _UNSAFE_METHODS
            and request.COOKIES.get("duo_access")
            and not request.headers.get("Authorization", "").startswith("Bearer ")
        ):
            origin = (request.headers.get("Origin") or "").rstrip("/")
            if not origin:
                origin = _origin_from_referer(request.headers.get("Referer", ""))
            if origin and origin not in self._trusted:
                logger.warning(
                    "blocked_cross_origin_cookie_request method=%s origin=%s path=%s",
                    request.method,
                    origin,
                    request.path,
                )
                return JsonResponse({"detail": "Forbidden origin."}, status=403)

        return self.get_response(request)
