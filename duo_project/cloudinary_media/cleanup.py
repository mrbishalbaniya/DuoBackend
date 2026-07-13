"""Delete Cloudinary assets when URLs are replaced or records removed."""

from __future__ import annotations

import logging

import cloudinary.uploader

from duo_project.cloudinary_media.delivery import parse_cloudinary_url

logger = logging.getLogger("duo.cloudinary")


def delete_cloudinary_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = parse_cloudinary_url(url)
    if not parsed:
        return False
    try:
        # Lazy import avoids circular import with cloudinary_upload.
        from duo_project.cloudinary_upload import _ensure_cloudinary_configured

        _ensure_cloudinary_configured()
        result = cloudinary.uploader.destroy(
            parsed["public_id"],
            resource_type=parsed["resource_type"],
            invalidate=True,
        )
        logger.info(
            "cloudinary_asset_deleted public_id=%s result=%s",
            parsed["public_id"],
            result.get("result"),
        )
        return result.get("result") == "ok"
    except Exception as exc:
        logger.warning(
            "cloudinary_delete_failed public_id=%s error=%s",
            parsed.get("public_id"),
            exc,
        )
        return False
