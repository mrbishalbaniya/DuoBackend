"""Safe APK URL resolution for admin and API layers."""

from __future__ import annotations

import logging

logger = logging.getLogger("update")


def resolve_apk_url(version) -> str:
    """Return a public APK URL without raising when storage is misconfigured."""
    url = (getattr(version, "apk_url", None) or "").strip()
    if url:
        return url

    apk_file = getattr(version, "apk_file", None)
    if not apk_file:
        return ""

    try:
        name = apk_file.name
        if not name:
            return ""
        return apk_file.url
    except Exception:
        logger.exception(
            "Failed to resolve APK file URL for AppVersion id=%s name=%s",
            getattr(version, "pk", None),
            getattr(apk_file, "name", ""),
        )
        return ""
