"""Cloudinary upload defaults and metadata extraction."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("duo.cloudinary")

# Applied at upload-time (stored asset optimization).
UPLOAD_TRANSFORMATION = {
    "quality": "auto:good",
    "fetch_format": "auto",
    "flags": "progressive",
}

# Video eager poster frame (async generation).
VIDEO_EAGER_THUMBNAIL = [
    {"width": 640, "height": 360, "crop": "fill", "format": "jpg", "quality": "auto"},
]


def upload_options_for_image(*, folder: str, public_id: str, **extra) -> dict[str, Any]:
    return {
        "folder": folder,
        "public_id": public_id,
        "resource_type": "image",
        "overwrite": False,
        "unique_filename": True,
        "use_filename": False,
        "invalidate": True,
        **UPLOAD_TRANSFORMATION,
        **extra,
    }


def upload_options_for_auto(*, folder: str, public_id: str, **extra) -> dict[str, Any]:
    return {
        "folder": folder,
        "public_id": public_id,
        "resource_type": "auto",
        "overwrite": False,
        "unique_filename": True,
        "use_filename": False,
        "invalidate": True,
        **extra,
    }


def upload_options_for_video(*, folder: str, public_id: str, **extra) -> dict[str, Any]:
    return {
        "folder": folder,
        "public_id": public_id,
        "resource_type": "video",
        "overwrite": False,
        "unique_filename": True,
        "use_filename": False,
        "invalidate": True,
        "eager": VIDEO_EAGER_THUMBNAIL,
        "eager_async": True,
        "quality": "auto",
        **extra,
    }


def metadata_from_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "public_id": result.get("public_id"),
        "resource_type": result.get("resource_type", "image"),
        "secure_url": result.get("secure_url"),
        "width": result.get("width"),
        "height": result.get("height"),
        "format": result.get("format"),
        "bytes": result.get("bytes"),
        "version": result.get("version"),
        "duration": result.get("duration"),
    }


def log_upload_success(*, kind: str, user_id: int, result: dict[str, Any]) -> None:
    logger.info(
        "cloudinary_upload_ok kind=%s user_id=%s public_id=%s bytes=%s",
        kind,
        user_id,
        result.get("public_id"),
        result.get("bytes"),
    )


def log_upload_failure(*, kind: str, user_id: int, error: Exception) -> None:
    logger.warning("cloudinary_upload_failed kind=%s user_id=%s error=%s", kind, user_id, error)


def log_destroy(*, public_id: str, result: dict[str, Any] | str) -> None:
    logger.info("cloudinary_destroy public_id=%s result=%s", public_id, result)
