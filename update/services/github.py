"""Fetch Duo mobile releases from GitHub (same source as DuoMobile fallback)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from update.models import AppVersion
from update.services.release_notes import (
    resolve_release_title,
    sanitize_release_notes,
)
from update.services.version import activate_version, publish_version

logger = logging.getLogger("update")

_TAG_RE = re.compile(
    r"^v?(?P<version>\d+(?:\.\d+){1,3})(?:[-_+]?build[.\-_]?(?P<build>\d+))?$",
    re.IGNORECASE,
)
_BUILD_IN_NAME_RE = re.compile(r"\bbuild\s*[#:]?\s*(\d+)\b", re.IGNORECASE)


@dataclass(frozen=True)
class GithubReleaseInfo:
    tag: str
    version: str
    build_number: int
    release_title: str
    release_notes: list[str]
    apk_url: str
    latest_apk_url: str
    html_url: str
    file_size_bytes: int
    checksum_sha256: str
    published_at: datetime | None
    raw: dict[str, Any]

    def as_admin_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "version": self.version,
            "build_number": self.build_number,
            "release_title": self.release_title,
            "release_notes": self.release_notes,
            "apk_url": self.apk_url,
            "latest_apk_url": self.latest_apk_url,
            "html_url": self.html_url,
            "file_size_bytes": self.file_size_bytes,
            "checksum_sha256": self.checksum_sha256,
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }


class GithubReleaseError(Exception):
    """Raised when GitHub release data cannot be fetched or parsed."""


def github_repo() -> str:
    return (getattr(settings, "GITHUB_MOBILE_REPO", None) or "mrbishalbaniya/duoflutter").strip()


def github_releases_page_url() -> str:
    return f"https://github.com/{github_repo()}/releases"


def github_latest_apk_url() -> str:
    asset = getattr(settings, "GITHUB_MOBILE_APK_ASSET", "app-release.apk")
    return f"https://github.com/{github_repo()}/releases/latest/download/{asset}"


def github_api_latest_url() -> str:
    return f"https://api.github.com/repos/{github_repo()}/releases/latest"


def parse_version_and_build(tag: str, *, name: str = "") -> tuple[str, int]:
    """
    Parse CI tags like ``v1.0.0-build.40`` into (version, build_number).

    Falls back to build number embedded in the release name.
    """
    cleaned = (tag or "").strip()
    match = _TAG_RE.match(cleaned)
    version = ""
    build = 0
    if match:
        version = match.group("version")
        if match.group("build"):
            build = int(match.group("build"))

    if not version:
        version = cleaned.lstrip("vV").split("-")[0].strip() or "0.0.0"

    if build <= 0:
        name_match = _BUILD_IN_NAME_RE.search(name or "")
        if name_match:
            build = int(name_match.group(1))

    if build <= 0:
        build = 1

    return version, build


def _extract_sha256(asset: dict[str, Any]) -> str:
    digest = (asset.get("digest") or "").strip()
    if digest.lower().startswith("sha256:"):
        return digest.split(":", 1)[1].strip().lower()
    return ""


def _parse_published_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    dt = parse_datetime(raw)
    if dt is None:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.utc)
    return dt


def fetch_latest_github_release(*, timeout: float = 20.0) -> GithubReleaseInfo:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "DuoBackend-OTA",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = (getattr(settings, "GITHUB_TOKEN", None) or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = github_api_latest_url()
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        raise GithubReleaseError(f"GitHub request failed: {exc}") from exc

    if response.status_code != 200:
        raise GithubReleaseError(
            f"GitHub API returned {response.status_code}: {(response.text or '')[:240]}"
        )

    data = response.json()
    if not isinstance(data, dict):
        raise GithubReleaseError("Unexpected GitHub release payload")

    tag = str(data.get("tag_name") or "").strip()
    if not tag:
        raise GithubReleaseError("Latest GitHub release has no tag_name")

    name = str(data.get("name") or "").strip()
    version, build_number = parse_version_and_build(tag, name=name)

    asset_name = getattr(settings, "GITHUB_MOBILE_APK_ASSET", "app-release.apk")
    apk_asset: dict[str, Any] | None = None
    for asset in data.get("assets") or []:
        if isinstance(asset, dict) and asset.get("name") == asset_name:
            apk_asset = asset
            break

    if apk_asset is None:
        raise GithubReleaseError(f"Release {tag} has no asset named {asset_name}")

    pin_url = str(apk_asset.get("browser_download_url") or "").strip()
    if not pin_url:
        pin_url = (
            f"https://github.com/{github_repo()}/releases/download/{tag}/{asset_name}"
        )

    body = str(data.get("body") or "")
    notes = sanitize_release_notes(body, with_fallback=True)
    title = resolve_release_title(name, version=version)

    return GithubReleaseInfo(
        tag=tag,
        version=version,
        build_number=build_number,
        release_title=title,
        release_notes=notes,
        apk_url=pin_url,
        latest_apk_url=github_latest_apk_url(),
        html_url=str(data.get("html_url") or f"https://github.com/{github_repo()}/releases/tag/{tag}"),
        file_size_bytes=int(apk_asset.get("size") or 0),
        checksum_sha256=_extract_sha256(apk_asset),
        published_at=_parse_published_at(data.get("published_at")),
        raw=data,
    )


@transaction.atomic
def sync_app_version_from_github(
    *,
    platform: str = AppVersion.PLATFORM_ANDROID,
    channel: str = AppVersion.CHANNEL_STABLE,
    activate: bool = True,
    publish: bool = True,
) -> tuple[AppVersion, GithubReleaseInfo, bool]:
    """
    Upsert AppVersion from the latest GitHub release.

    Returns (row, release, created).
    """
    release = fetch_latest_github_release()
    existing = (
        AppVersion.objects.select_for_update()
        .filter(
            platform=platform,
            channel=channel,
            version=release.version,
            build_number=release.build_number,
        )
        .first()
    )
    created = existing is None
    row = existing or AppVersion(
        platform=platform,
        channel=channel,
        version=release.version,
        build_number=release.build_number,
    )

    row.apk_url = release.apk_url
    row.file_size_bytes = release.file_size_bytes or row.file_size_bytes
    if release.checksum_sha256:
        row.checksum_sha256 = release.checksum_sha256
    if release.release_title:
        row.release_title = release.release_title
    # Keep admin-edited notes if already present; otherwise store sanitized GitHub notes.
    if created or not row.normalized_release_notes():
        row.release_notes = release.release_notes
    if release.published_at and not row.published_at:
        row.published_at = release.published_at
    if not (row.minimum_version or "").strip():
        row.minimum_version = release.version
    row.soft_update = True
    row.save()

    if publish:
        publish_version(row, activate=False)
    if activate:
        activate_version(row)

    logger.info(
        "Synced AppVersion from GitHub tag=%s version=%s build=%s created=%s",
        release.tag,
        release.version,
        release.build_number,
        created,
    )
    return row, release, created
