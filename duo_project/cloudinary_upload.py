"""Upload files to Cloudinary (all user media — no local DuoBackend/media storage)."""

from __future__ import annotations

import mimetypes
import os

import cloudinary
import cloudinary.uploader
from duo_project.runtime_config import get_integration_settings

PROFILE_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
CHAT_MEDIA_TYPES = PROFILE_IMAGE_TYPES | {
    "audio/webm",
    "audio/ogg",
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "video/webm",
}
MAX_PROFILE_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_CHAT_UPLOAD_BYTES = 25 * 1024 * 1024


class CloudinaryNotConfiguredError(Exception):
    pass


def _ensure_configured() -> None:
    cfg = get_integration_settings()
    cloud_name = cfg.cloudinary_cloud_name
    api_key = cfg.cloudinary_api_key
    api_secret = cfg.cloudinary_api_secret

    if not cloud_name or not api_key or not api_secret:
        raise CloudinaryNotConfiguredError(
            "Cloudinary is not configured. Set credentials in Admin → Integration settings "
            "or CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET in .env."
        )

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )


def _guess_content_type(uploaded_file) -> str:
    content_type = getattr(uploaded_file, "content_type", None)
    if content_type:
        return content_type.split(";")[0].strip().lower()

    name = getattr(uploaded_file, "name", "") or ""
    guessed, _ = mimetypes.guess_type(name)
    return (guessed or "application/octet-stream").lower()


def _validate_upload(uploaded_file, *, allowed_types: set[str], max_bytes: int) -> str:
    if not uploaded_file:
        raise ValueError("No file provided.")

    size = getattr(uploaded_file, "size", None)
    if size is not None and size > max_bytes:
        raise ValueError(f"File is too large. Maximum size is {max_bytes // (1024 * 1024)} MB.")

    content_type = _guess_content_type(uploaded_file)
    if content_type not in allowed_types:
        raise ValueError("Unsupported file type.")

    return content_type


def _safe_stem(filename: str) -> str:
    stem = os.path.splitext(os.path.basename(filename or "upload"))[0]
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem)
    return safe[:80] or "upload"


def _upload_kwargs(**options):
    kwargs = dict(options)
    preset = get_integration_settings().cloudinary_upload_preset
    if preset:
        kwargs["upload_preset"] = preset
    return kwargs


def upload_profile_photo(uploaded_file, *, user_id: int) -> str:
    _ensure_configured()
    cfg = get_integration_settings()
    content_type = _validate_upload(
        uploaded_file,
        allowed_types=PROFILE_IMAGE_TYPES,
        max_bytes=MAX_PROFILE_UPLOAD_BYTES,
    )

    stem = _safe_stem(getattr(uploaded_file, "name", "photo"))
    result = cloudinary.uploader.upload(
        uploaded_file,
        **_upload_kwargs(
            folder=cfg.cloudinary_profile_folder,
            public_id=f"user_{user_id}_{stem}",
            resource_type="image",
            overwrite=True,
            unique_filename=True,
            use_filename=False,
            format=content_type.split("/")[-1] if content_type.startswith("image/") else None,
        ),
    )
    return result["secure_url"]


def upload_verification_selfie(uploaded_file, *, user_id: int) -> str:
    _ensure_configured()
    cfg = get_integration_settings()
    content_type = _validate_upload(
        uploaded_file,
        allowed_types=PROFILE_IMAGE_TYPES,
        max_bytes=MAX_PROFILE_UPLOAD_BYTES,
    )

    stem = _safe_stem(getattr(uploaded_file, "name", "selfie"))
    result = cloudinary.uploader.upload(
        uploaded_file,
        **_upload_kwargs(
            folder=cfg.cloudinary_verification_folder,
            public_id=f"verify_{user_id}_{stem}",
            resource_type="image",
            overwrite=True,
            unique_filename=True,
            use_filename=False,
            format=content_type.split("/")[-1] if content_type.startswith("image/") else None,
        ),
    )
    return result["secure_url"]


def upload_chat_media(uploaded_file, *, user_id: int) -> str:
    _ensure_configured()
    cfg = get_integration_settings()
    _validate_upload(
        uploaded_file,
        allowed_types=CHAT_MEDIA_TYPES,
        max_bytes=MAX_CHAT_UPLOAD_BYTES,
    )

    stem = _safe_stem(getattr(uploaded_file, "name", "media"))

    result = cloudinary.uploader.upload(
        uploaded_file,
        **_upload_kwargs(
            folder=cfg.cloudinary_chat_folder,
            public_id=f"user_{user_id}_{stem}",
            resource_type="auto",
            overwrite=True,
            unique_filename=True,
            use_filename=False,
        ),
    )
    return result["secure_url"]
