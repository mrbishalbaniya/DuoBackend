"""Security-focused HTTP middleware."""

from __future__ import annotations

from django.conf import settings


class SecurityHeadersMiddleware:
    """Add defense-in-depth headers for API responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if not settings.DEBUG:
            response.headers.setdefault(
                "Permissions-Policy",
                "camera=(self), microphone=(self), geolocation=(self)",
            )
            # Restrictive CSP is for JSON API responses only. Applying it to
            # /admin/ blocks all CSS, JS, images, and form submissions.
            if request.path.startswith("/api/"):
                response.headers.setdefault(
                    "Content-Security-Policy",
                    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
                )
        return response
