"""Cloudflare R2 media storage configuration."""

from __future__ import annotations

from django.conf import settings


def media_storage_backend() -> str:
    backend = (getattr(settings, "MEDIA_STORAGE_BACKEND", "cloudinary") or "cloudinary").lower()
    if backend == "r2" and not r2_is_configured():
        return "cloudinary"
    return backend


def r2_is_configured() -> bool:
    return bool(
        getattr(settings, "R2_BUCKET_NAME", "")
        and getattr(settings, "R2_ACCESS_KEY_ID", "")
        and getattr(settings, "R2_SECRET_ACCESS_KEY", "")
        and getattr(settings, "R2_ENDPOINT_URL", "")
        and getattr(settings, "R2_PUBLIC_URL", "")
    )


def r2_profile_prefix() -> str:
    return getattr(settings, "R2_PROFILE_PREFIX", "profile_photos")


def r2_chat_prefix() -> str:
    return getattr(settings, "R2_CHAT_PREFIX", "chat_media")


def r2_verification_prefix() -> str:
    return getattr(settings, "R2_VERIFICATION_PREFIX", "verification_selfies")


def r2_location_prefix() -> str:
    return getattr(settings, "R2_LOCATION_PREFIX", "duo")


def build_public_url(object_key: str) -> str:
    base = getattr(settings, "R2_PUBLIC_URL", "").rstrip("/")
    key = object_key.lstrip("/")
    return f"{base}/{key}"
