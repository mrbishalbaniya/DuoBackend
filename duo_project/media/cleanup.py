"""Delete orphaned R2 media when URLs are replaced."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from django.conf import settings

from .config import build_public_url
from .r2_client import delete_prefix

logger = logging.getLogger("duo.media")


def is_managed_media_url(url: str | None) -> bool:
    if not url:
        return False
    public_base = getattr(settings, "R2_PUBLIC_URL", "").rstrip("/")
    if not public_base:
        return False
    return url.startswith(public_base + "/")


def url_to_object_prefix(url: str) -> str | None:
    if not is_managed_media_url(url):
        return None
    public_base = getattr(settings, "R2_PUBLIC_URL", "").rstrip("/")
    path = urlparse(url).path.lstrip("/")
    base_path = urlparse(public_base).path.lstrip("/")
    if base_path and path.startswith(base_path + "/"):
        path = path[len(base_path) + 1 :]
    parts = path.split("/")
    if len(parts) < 2:
        return None
    # .../folder/user_id/asset_id/variant.webp → prefix through asset_id
    return "/".join(parts[:-1])


def delete_media_at_url(url: str | None) -> None:
    prefix = url_to_object_prefix(url or "")
    if not prefix:
        return
    count = delete_prefix(prefix)
    if count:
        logger.info("r2_media_deleted prefix=%s count=%s", prefix, count)


def rebuild_variant_url(base_prefix: str, variant: str, ext: str = "webp") -> str:
    return build_public_url(f"{base_prefix}/{variant}.{ext}")
