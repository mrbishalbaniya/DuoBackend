"""Upload files to Cloudinary (all user media — no local DuoBackend/media storage)."""

from __future__ import annotations

import mimetypes
import os

import cloudinary
import cloudinary.uploader
from django.conf import settings

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
    cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", "")
    api_key = getattr(settings, "CLOUDINARY_API_KEY", "")
    api_secret = getattr(settings, "CLOUDINARY_API_SECRET", "")

    if not cloud_name or not api_key or not api_secret:
        raise CloudinaryNotConfiguredError(
            "Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, "
            "CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET in DuoBackend/.env"
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
    preset = getattr(settings, "CLOUDINARY_UPLOAD_PRESET", "")
    if preset:
        kwargs["upload_preset"] = preset
    return kwargs


def upload_profile_photo(uploaded_file, *, user_id: int) -> str:
    _ensure_configured()
    content_type = _validate_upload(
        uploaded_file,
        allowed_types=PROFILE_IMAGE_TYPES,
        max_bytes=MAX_PROFILE_UPLOAD_BYTES,
    )

    stem = _safe_stem(getattr(uploaded_file, "name", "photo"))
    result = cloudinary.uploader.upload(
        uploaded_file,
        **_upload_kwargs(
            folder=settings.CLOUDINARY_PROFILE_FOLDER,
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
    content_type = _validate_upload(
        uploaded_file,
        allowed_types=PROFILE_IMAGE_TYPES,
        max_bytes=MAX_PROFILE_UPLOAD_BYTES,
    )

    stem = _safe_stem(getattr(uploaded_file, "name", "selfie"))
    folder = getattr(settings, "CLOUDINARY_VERIFICATION_FOLDER", "duo/verification_selfies")
    result = cloudinary.uploader.upload(
        uploaded_file,
        **_upload_kwargs(
            folder=folder,
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
    _validate_upload(
        uploaded_file,
        allowed_types=CHAT_MEDIA_TYPES,
        max_bytes=MAX_CHAT_UPLOAD_BYTES,
    )

    stem = _safe_stem(getattr(uploaded_file, "name", "media"))

    result = cloudinary.uploader.upload(
        uploaded_file,
        **_upload_kwargs(
            folder=settings.CLOUDINARY_CHAT_FOLDER,
            public_id=f"user_{user_id}_{stem}",
            resource_type="auto",
            overwrite=True,
            unique_filename=True,
            use_filename=False,
        ),
    )
    return result["secure_url"]
