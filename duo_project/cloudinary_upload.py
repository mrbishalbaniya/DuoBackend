"""Upload files to Cloudinary or Cloudflare R2 (configurable via MEDIA_STORAGE_BACKEND)."""

from __future__ import annotations

import mimetypes
import uuid

import cloudinary
import cloudinary.uploader
from django.conf import settings

from duo_project.cloudinary_media.cleanup import delete_cloudinary_url
from duo_project.cloudinary_media.responses import MediaUploadResponse
from duo_project.cloudinary_media.upload_options import (
    log_upload_failure,
    log_upload_success,
    metadata_from_result,
    upload_options_for_auto,
    upload_options_for_image,
    upload_options_for_video,
)
from duo_project.media.config import media_storage_backend
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
    "video/mp4",
    "video/quicktime",
}
MAX_PROFILE_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_CHAT_UPLOAD_BYTES = 25 * 1024 * 1024


class CloudinaryNotConfiguredError(Exception):
    """Raised when the active media backend is not configured."""


def _ensure_cloudinary_configured() -> None:
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
    from duo_project.media.validation import validate_upload

    return validate_upload(uploaded_file, allowed_types=allowed_types, max_bytes=max_bytes)


def _validate_profile_image(uploaded_file) -> str:
    from duo_project.media.validation import validate_image_dimensions, validate_upload

    content_type = validate_upload(
        uploaded_file,
        allowed_types=PROFILE_IMAGE_TYPES,
        max_bytes=MAX_PROFILE_UPLOAD_BYTES,
    )
    validate_image_dimensions(uploaded_file, min_width=200, min_height=200)
    return content_type


def _safe_stem(filename: str) -> str:
    from duo_project.media.validation import safe_stem

    return safe_stem(filename)


def _upload_kwargs(**options):
    kwargs = dict(options)
    preset = get_integration_settings().cloudinary_upload_preset
    if preset:
        kwargs["upload_preset"] = preset
    return kwargs


def _unique_public_id(prefix: str, stem: str) -> str:
    return f"{prefix}_{stem}_{uuid.uuid4().hex[:10]}"


def _upload_profile_photo_cloudinary(
    uploaded_file, *, user_id: int, replace_url: str | None = None
) -> MediaUploadResponse:
    _ensure_cloudinary_configured()
    cfg = get_integration_settings()
    _validate_profile_image(uploaded_file)

    stem = _safe_stem(getattr(uploaded_file, "name", "photo"))
    public_id = _unique_public_id(f"user_{user_id}", stem)
    try:
        result = cloudinary.uploader.upload(
            uploaded_file,
            **_upload_kwargs(
                **upload_options_for_image(
                    folder=cfg.cloudinary_profile_folder,
                    public_id=public_id,
                ),
            ),
        )
        log_upload_success(kind="profile_photo", user_id=user_id, result=result)
    except Exception as exc:
        log_upload_failure(kind="profile_photo", user_id=user_id, error=exc)
        raise

    if replace_url:
        delete_cloudinary_url(replace_url)

    return MediaUploadResponse(
        image_url=result["secure_url"],
        media=metadata_from_result(result),
    )


def _upload_verification_selfie_cloudinary(uploaded_file, *, user_id: int) -> MediaUploadResponse:
    _ensure_cloudinary_configured()
    cfg = get_integration_settings()
    _validate_profile_image(uploaded_file)

    stem = _safe_stem(getattr(uploaded_file, "name", "selfie"))
    public_id = _unique_public_id(f"verify_{user_id}", stem)
    try:
        result = cloudinary.uploader.upload(
            uploaded_file,
            **_upload_kwargs(
                **upload_options_for_image(
                    folder=cfg.cloudinary_verification_folder,
                    public_id=public_id,
                ),
            ),
        )
        log_upload_success(kind="verification_selfie", user_id=user_id, result=result)
    except Exception as exc:
        log_upload_failure(kind="verification_selfie", user_id=user_id, error=exc)
        raise

    return MediaUploadResponse(
        image_url=result["secure_url"],
        media=metadata_from_result(result),
    )


def _upload_chat_media_cloudinary(uploaded_file, *, user_id: int) -> MediaUploadResponse:
    _ensure_cloudinary_configured()
    cfg = get_integration_settings()
    content_type = _validate_upload(
        uploaded_file,
        allowed_types=CHAT_MEDIA_TYPES,
        max_bytes=MAX_CHAT_UPLOAD_BYTES,
    )

    stem = _safe_stem(getattr(uploaded_file, "name", "media"))
    public_id = _unique_public_id(f"user_{user_id}", stem)

    if content_type.startswith("video/"):
        options = upload_options_for_video(
            folder=cfg.cloudinary_chat_folder,
            public_id=public_id,
        )
    elif content_type.startswith("image/"):
        from duo_project.media.validation import validate_image_dimensions

        validate_image_dimensions(uploaded_file, min_width=32, min_height=32)
        options = upload_options_for_image(
            folder=cfg.cloudinary_chat_folder,
            public_id=public_id,
        )
    else:
        options = upload_options_for_auto(
            folder=cfg.cloudinary_chat_folder,
            public_id=public_id,
        )

    try:
        result = cloudinary.uploader.upload(
            uploaded_file,
            **_upload_kwargs(**options),
        )
        log_upload_success(kind="chat_media", user_id=user_id, result=result)
    except Exception as exc:
        log_upload_failure(kind="chat_media", user_id=user_id, error=exc)
        raise

    return MediaUploadResponse(
        image_url=result["secure_url"],
        media=metadata_from_result(result),
    )


def upload_profile_photo_result(
    uploaded_file, *, user_id: int, replace_url: str | None = None
) -> MediaUploadResponse:
    if media_storage_backend() == "r2":
        from duo_project.media.r2_client import R2NotConfiguredError
        from duo_project.media.upload import ensure_r2_ready, upload_profile_photo_r2

        try:
            ensure_r2_ready()
            url = upload_profile_photo_r2(
                uploaded_file, user_id=user_id, replace_url=replace_url
            )
            return MediaUploadResponse(image_url=url)
        except R2NotConfiguredError as exc:
            raise CloudinaryNotConfiguredError(str(exc)) from exc
    return _upload_profile_photo_cloudinary(
        uploaded_file, user_id=user_id, replace_url=replace_url
    )


def upload_verification_selfie_result(uploaded_file, *, user_id: int) -> MediaUploadResponse:
    if media_storage_backend() == "r2":
        from duo_project.media.r2_client import R2NotConfiguredError
        from duo_project.media.upload import ensure_r2_ready, upload_verification_selfie_r2

        try:
            ensure_r2_ready()
            url = upload_verification_selfie_r2(uploaded_file, user_id=user_id)
            return MediaUploadResponse(image_url=url)
        except R2NotConfiguredError as exc:
            raise CloudinaryNotConfiguredError(str(exc)) from exc
    return _upload_verification_selfie_cloudinary(uploaded_file, user_id=user_id)


def upload_chat_media_result(uploaded_file, *, user_id: int) -> MediaUploadResponse:
    if media_storage_backend() == "r2":
        from duo_project.media.r2_client import R2NotConfiguredError
        from duo_project.media.upload import ensure_r2_ready, upload_chat_media_r2

        try:
            ensure_r2_ready()
            url = upload_chat_media_r2(uploaded_file, user_id=user_id)
            return MediaUploadResponse(image_url=url)
        except R2NotConfiguredError as exc:
            raise CloudinaryNotConfiguredError(str(exc)) from exc
    return _upload_chat_media_cloudinary(uploaded_file, user_id=user_id)


def upload_profile_photo(
    uploaded_file, *, user_id: int, replace_url: str | None = None
) -> str:
    return upload_profile_photo_result(
        uploaded_file, user_id=user_id, replace_url=replace_url
    ).image_url


def upload_verification_selfie(uploaded_file, *, user_id: int) -> str:
    return upload_verification_selfie_result(uploaded_file, user_id=user_id).image_url


def upload_chat_media(uploaded_file, *, user_id: int) -> str:
    return upload_chat_media_result(uploaded_file, user_id=user_id).image_url
