"""Version publish, activate, rollback helpers."""

from __future__ import annotations

import hashlib
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from update.models import AppVersion
from update.services.admin_helpers import resolve_apk_url
from update.services.release_notes import (
    parse_release_notes,
    resolve_release_title,
    sanitize_release_notes,
)

__all__ = [
    "parse_release_notes",
    "resolve_release_title",
    "sanitize_release_notes",
    "compute_sha256",
    "compare_versions",
    "get_active_version",
    "get_minimum_active_version",
    "publish_version",
    "activate_version",
    "rollback_version",
    "version_payload",
    "update_required",
    "update_blocked",
]


def compute_sha256(file_obj) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    for chunk in file_obj.chunks():
        digest.update(chunk)
        size += len(chunk)
    file_obj.seek(0)
    return digest.hexdigest(), size


def compare_versions(left: str, right: str) -> int:
    """Return -1 if left < right, 0 if equal, 1 if left > right."""

    def parts(value: str) -> list[int]:
        nums: list[int] = []
        for token in value.strip().split("."):
            digits = "".join(ch for ch in token if ch.isdigit())
            nums.append(int(digits) if digits else 0)
        return nums or [0]

    a = parts(left)
    b = parts(right)
    length = max(len(a), len(b))
    a.extend([0] * (length - len(a)))
    b.extend([0] * (length - len(b)))
    for x, y in zip(a, b):
        if x < y:
            return -1
        if x > y:
            return 1
    return 0


def get_active_version(*, platform: str, channel: str = AppVersion.CHANNEL_STABLE) -> AppVersion | None:
    return (
        AppVersion.objects.filter(
            platform=platform,
            channel=channel,
            is_active=True,
            is_published=True,
        )
        .order_by("-build_number")
        .first()
    )


def get_minimum_active_version(platform: str) -> AppVersion | None:
    active = get_active_version(platform=platform)
    if active is None:
        return None
    minimum = (active.minimum_version or "").strip()
    if not minimum:
        return active
    candidates = AppVersion.objects.filter(
        platform=platform,
        channel=active.channel,
        is_published=True,
    )
    floor = None
    for item in candidates:
        if compare_versions(item.version, minimum) >= 0:
            if floor is None or item.build_number < floor.build_number:
                floor = item
    return floor or active


@transaction.atomic
def publish_version(version: AppVersion, *, activate: bool = True) -> AppVersion:
    version.is_published = True
    version.published_at = timezone.now()
    if activate:
        AppVersion.objects.filter(
            platform=version.platform,
            channel=version.channel,
            is_active=True,
        ).exclude(pk=version.pk).update(is_active=False)
        version.is_active = True
    version.save()
    return version


@transaction.atomic
def activate_version(version: AppVersion) -> AppVersion:
    AppVersion.objects.filter(
        platform=version.platform,
        channel=version.channel,
        is_active=True,
    ).exclude(pk=version.pk).update(is_active=False)
    version.is_active = True
    version.is_published = True
    if not version.published_at:
        version.published_at = timezone.now()
    version.save()
    return version


@transaction.atomic
def rollback_version(*, platform: str, channel: str = AppVersion.CHANNEL_STABLE) -> AppVersion | None:
    current = get_active_version(platform=platform, channel=channel)
    if current is None:
        return None
    previous = (
        AppVersion.objects.filter(
            platform=platform,
            channel=channel,
            is_published=True,
            build_number__lt=current.build_number,
        )
        .order_by("-build_number")
        .first()
    )
    if previous is None:
        return None
    return activate_version(previous)


def version_payload(version: AppVersion, *, request=None) -> dict:
    apk_url = resolve_apk_url(version)
    if request is not None and apk_url.startswith("/"):
        apk_url = request.build_absolute_uri(apk_url)

    title = resolve_release_title(
        getattr(version, "release_title", "") or "",
        version=version.version,
    )
    notes = sanitize_release_notes(version.release_notes)

    return {
        "latest_version": version.version,
        "minimum_version": version.minimum_version or version.version,
        "build_number": version.build_number,
        "apk_url": apk_url,
        "title": title,
        "release_title": title,
        "release_notes": notes,
        "force_update": version.force_update,
        "soft_update": version.soft_update,
        "emergency_update": version.emergency_update,
        "file_size": version.file_size_label,
        "file_size_bytes": version.file_size_bytes,
        "checksum_sha256": version.checksum_sha256,
        "published_at": version.published_at,
        "channel": version.channel,
        "platform": version.platform,
        "download_count": version.download_count,
        "mandatory": bool(version.force_update or version.emergency_update),
        "size": version.file_size_label,
        "version": version.version,
        "build": version.build_number,
    }


def update_required(
    *,
    installed_version: str,
    installed_build: int,
    latest: AppVersion,
) -> bool:
    if latest.build_number > installed_build:
        return True
    return compare_versions(installed_version, latest.version) < 0


def update_blocked(
    *,
    installed_version: str,
    installed_build: int,
    latest: AppVersion,
) -> bool:
    if latest.force_update or latest.emergency_update:
        return update_required(
            installed_version=installed_version,
            installed_build=installed_build,
            latest=latest,
        )
    minimum = (latest.minimum_version or "").strip()
    if not minimum:
        return False
    if compare_versions(installed_version, minimum) < 0:
        return True
    return installed_build < latest.build_number and latest.force_update
