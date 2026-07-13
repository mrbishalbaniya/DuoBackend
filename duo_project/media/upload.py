"""R2 upload orchestration."""

from __future__ import annotations

import uuid

from django.conf import settings

from .cleanup import delete_media_at_url
from .config import (
    build_public_url,
    r2_chat_prefix,
    r2_location_prefix,
    r2_profile_prefix,
    r2_verification_prefix,
)
from .image_processing import primary_delivery_variant, process_image_variants
from .r2_client import CACHE_IMMUTABLE, CACHE_STANDARD, R2NotConfiguredError, put_object
from .validation import (
    CHAT_MEDIA_TYPES,
    MAX_CHAT_UPLOAD_BYTES,
    MAX_PROFILE_UPLOAD_BYTES,
    PROFILE_IMAGE_TYPES,
    is_audio_type,
    is_image_type,
    is_video_type,
    safe_stem,
    validate_upload,
)
from .video_processing import extract_video_thumbnail


class MediaUploadResult:
    __slots__ = ("primary_url", "variants", "object_prefix")

    def __init__(self, *, primary_url: str, variants: dict[str, str], object_prefix: str):
        self.primary_url = primary_url
        self.variants = variants
        self.object_prefix = object_prefix


def _asset_prefix(folder: str, user_id: int, asset_id: str) -> str:
    return f"{r2_location_prefix()}/{folder}/{user_id}/{asset_id}"


def _upload_image_variants(
    uploaded_file,
    *,
    folder: str,
    user_id: int,
    replace_url: str | None = None,
) -> MediaUploadResult:
    content_type = validate_upload(
        uploaded_file,
        allowed_types=PROFILE_IMAGE_TYPES,
        max_bytes=MAX_PROFILE_UPLOAD_BYTES,
    )
    animated_gif = content_type == "image/gif"
    variants = process_image_variants(uploaded_file, animated_gif=animated_gif)

    asset_id = uuid.uuid4().hex
    prefix = _asset_prefix(folder, user_id, asset_id)
    url_map: dict[str, str] = {}

    for variant in variants:
        ext = "gif" if variant.content_type == "image/gif" else "webp"
        key = f"{prefix}/{variant.name}.{ext}"
        url_map[variant.name] = put_object(
            key=key,
            body=variant.data,
            content_type=variant.content_type,
            cache_control=CACHE_IMMUTABLE,
        )

    primary = primary_delivery_variant(variants)
    ext = "gif" if primary.content_type == "image/gif" else "webp"
    primary_url = url_map.get(primary.name) or build_public_url(f"{prefix}/{primary.name}.{ext}")

    if replace_url:
        delete_media_at_url(replace_url)

    return MediaUploadResult(primary_url=primary_url, variants=url_map, object_prefix=prefix)


def _upload_binary(
    uploaded_file,
    *,
    folder: str,
    user_id: int,
    content_type: str,
    max_bytes: int,
) -> MediaUploadResult:
    validate_upload(uploaded_file, allowed_types={content_type}, max_bytes=max_bytes)
    uploaded_file.seek(0)
    raw = uploaded_file.read()
    stem = safe_stem(getattr(uploaded_file, "name", "media"))
    asset_id = f"{stem}_{uuid.uuid4().hex[:12]}"
    prefix = _asset_prefix(folder, user_id, asset_id)
    ext = content_type.split("/")[-1]
    key = f"{prefix}/original.{ext}"
    url = put_object(
        key=key,
        body=raw,
        content_type=content_type,
        cache_control=CACHE_STANDARD,
    )
    variants = {"original": url}

    if is_video_type(content_type):
        thumb = extract_video_thumbnail(uploaded_file)
        if thumb:
            thumb_key = f"{prefix}/thumb.webp"
            variants["thumb"] = put_object(
                key=thumb_key,
                body=thumb,
                content_type="image/webp",
                cache_control=CACHE_IMMUTABLE,
            )

    return MediaUploadResult(primary_url=url, variants=variants, object_prefix=prefix)


def upload_profile_photo_r2(uploaded_file, *, user_id: int, replace_url: str | None = None) -> str:
    result = _upload_image_variants(
        uploaded_file,
        folder=r2_profile_prefix(),
        user_id=user_id,
        replace_url=replace_url,
    )
    return result.primary_url


def upload_verification_selfie_r2(uploaded_file, *, user_id: int) -> str:
    result = _upload_image_variants(
        uploaded_file,
        folder=r2_verification_prefix(),
        user_id=user_id,
    )
    return result.primary_url


def upload_chat_media_r2(uploaded_file, *, user_id: int) -> str:
    content_type = validate_upload(
        uploaded_file,
        allowed_types=CHAT_MEDIA_TYPES,
        max_bytes=MAX_CHAT_UPLOAD_BYTES,
    )

    if is_image_type(content_type):
        result = _upload_image_variants(
            uploaded_file,
            folder=r2_chat_prefix(),
            user_id=user_id,
        )
        return result.primary_url

    if is_audio_type(content_type) or is_video_type(content_type):
        result = _upload_binary(
            uploaded_file,
            folder=r2_chat_prefix(),
            user_id=user_id,
            content_type=content_type,
            max_bytes=MAX_CHAT_UPLOAD_BYTES,
        )
        return result.primary_url

    raise ValueError("Unsupported file type.")


def ensure_r2_ready() -> None:
    if not getattr(settings, "R2_BUCKET_NAME", ""):
        raise R2NotConfiguredError(
            "Cloudflare R2 is not configured. Set R2_BUCKET_NAME, R2_ACCESS_KEY_ID, "
            "R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL, and R2_PUBLIC_URL in .env."
        )
