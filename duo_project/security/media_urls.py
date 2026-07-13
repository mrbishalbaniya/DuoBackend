"""Validate user-supplied media URLs against trusted CDN origins."""

from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings


def _trusted_media_hosts() -> set[str]:
    hosts: set[str] = {
        "res.cloudinary.com",
        "lh3.googleusercontent.com",
    }
    frontend = getattr(settings, "FRONTEND_URL", "").strip().rstrip("/")
    if frontend:
        hosts.add(urlparse(frontend).netloc.lower())
    r2_public = getattr(settings, "R2_PUBLIC_URL", "").strip()
    if r2_public:
        hosts.add(urlparse(r2_public).netloc.lower())
    extra = getattr(settings, "TRUSTED_MEDIA_HOSTS", "")
    for part in str(extra).split(","):
        host = part.strip().lower()
        if host:
            hosts.add(host)
    return hosts


def is_allowed_media_url(url: str | None) -> bool:
    """Return True for empty URLs or URLs on trusted media hosts."""
    trimmed = (url or "").strip()
    if not trimmed:
        return True
    if trimmed.startswith("/media/"):
        return False
    parsed = urlparse(trimmed)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.netloc or "").lower()
    if not host:
        return False
    return host in _trusted_media_hosts()


def validate_media_url_or_raise(url: str | None, *, field: str = "image_url") -> str:
    trimmed = (url or "").strip()
    if not trimmed:
        return ""
    if not is_allowed_media_url(trimmed):
        raise ValueError(f"Unsupported {field} host.")
    return trimmed
