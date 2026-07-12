"""Configurable APK storage backends (local, S3, R2, DigitalOcean Spaces)."""

from __future__ import annotations

import mimetypes
from typing import BinaryIO

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


def build_apk_filename(version: str, build_number: int) -> str:
    safe_version = version.replace("/", "-").strip()
    return f"duo-v{safe_version}-b{build_number}.apk"


def save_apk_file(*, version: str, build_number: int, uploaded_file) -> tuple[str, str]:
    """Persist APK and return (relative_path, public_url)."""
    filename = build_apk_filename(version, build_number)
    saved_name = default_storage.save(f"apk/{filename}", uploaded_file)
    return saved_name, default_storage.url(saved_name)


def save_apk_bytes(*, version: str, build_number: int, data: bytes) -> tuple[str, str]:
    filename = build_apk_filename(version, build_number)
    saved_name = default_storage.save(f"apk/{filename}", ContentFile(data))
    return saved_name, default_storage.url(saved_name)


def guess_apk_mime() -> str:
    return mimetypes.guess_type("app.apk")[0] or "application/vnd.android.package-archive"
