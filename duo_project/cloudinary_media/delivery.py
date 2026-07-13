"""Cloudinary delivery URL transforms and presets (dynamic — no duplicate storage)."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

# Named presets map to Cloudinary transformation chains.
PRESETS: dict[str, dict[str, Any]] = {
    "thumb": {"width": 96, "height": 96, "crop": "fill", "gravity": "face"},
    "avatar": {"width": 128, "height": 128, "crop": "fill", "gravity": "face"},
    "small": {"width": 320, "height": 400, "crop": "fill", "gravity": "auto"},
    "medium": {"width": 640, "height": 800, "crop": "fill", "gravity": "auto"},
    "large": {"width": 1080, "height": 1350, "crop": "limit"},
    "discover_card": {"width": 480, "height": 600, "crop": "fill", "gravity": "auto"},
    "match_card": {"width": 420, "height": 560, "crop": "fill", "gravity": "face"},
    "chat_preview": {"width": 480, "height": 480, "crop": "limit"},
    "gallery": {"width": 720, "height": 900, "crop": "limit"},
    "verification": {"width": 512, "height": 512, "crop": "fill", "gravity": "face"},
}

DEFAULT_DELIVERY = {
    "fetch_format": "auto",
    "quality": "auto:good",
    "flags": "progressive",
    "dpr": "auto",
}

_TRANSFORM_SEGMENT_RE = re.compile(
    r"^(?:[a-z]{1,3}_[^,/]+)(?:,[a-z]{1,3}_[^,/]+)*$"
)
_CLOUDINARY_UPLOAD_RE = re.compile(
    r"/(?P<resource_type>image|video|raw)/upload/(?:(?:[^/]+)/)*(?:v(?P<version>\d+)/)?(?P<public_id>.+)$"
)


def is_cloudinary_url(url: str | None) -> bool:
    return bool(url and "res.cloudinary.com" in url)


def _is_transformation_segment(segment: str) -> bool:
    if not segment:
        return False
    if segment.startswith("v") and segment[1:].isdigit():
        return False
    return bool(_TRANSFORM_SEGMENT_RE.match(segment))


def parse_cloudinary_url(url: str) -> dict[str, Any] | None:
    """Extract public_id, resource_type, version from a delivery URL."""
    if not is_cloudinary_url(url):
        return None
    path = urlparse(url).path
    match = _CLOUDINARY_UPLOAD_RE.search(path)
    if not match:
        return None
    public_id = match.group("public_id")
    if "." in public_id.rsplit("/", 1)[-1]:
        public_id = public_id.rsplit(".", 1)[0]
    return {
        "public_id": public_id,
        "resource_type": match.group("resource_type"),
        "version": int(match.group("version")) if match.group("version") else None,
        "secure_url": url,
    }


def build_transformation_string(preset: str | None = None, **overrides: Any) -> str:
    parts: dict[str, Any] = dict(DEFAULT_DELIVERY)
    if preset and preset in PRESETS:
        parts.update(PRESETS[preset])
    parts.update(overrides)

    segments: list[str] = []
    if parts.get("width"):
        segments.append(f"w_{parts['width']}")
    if parts.get("height"):
        segments.append(f"h_{parts['height']}")
    if parts.get("crop"):
        segments.append(f"c_{parts['crop']}")
    if parts.get("gravity"):
        segments.append(f"g_{parts['gravity']}")
    if parts.get("fetch_format"):
        segments.append(f"f_{parts['fetch_format']}")
    if parts.get("quality"):
        segments.append(f"q_{parts['quality']}")
    if parts.get("dpr"):
        segments.append(f"dpr_{parts['dpr']}")
    if parts.get("flags"):
        segments.append(f"fl_{parts['flags']}")
    return ",".join(segments)


def delivery_url(
    url: str | None,
    *,
    preset: str | None = None,
    **overrides: Any,
) -> str | None:
    """Return an optimized Cloudinary URL with dynamic transforms."""
    if not url:
        return None
    if not is_cloudinary_url(url):
        return url

    transform = build_transformation_string(preset, **overrides)
    if not transform:
        return url

    base, sep, rest = url.partition("/upload/")
    if not sep:
        return url

    segments = rest.split("/")
    while segments and _is_transformation_segment(segments[0]):
        segments.pop(0)

    suffix = "/".join(segments)
    return f"{base}/upload/{transform}/{suffix}"


def video_poster_url(url: str | None) -> str | None:
    if not url or not is_cloudinary_url(url):
        return None
    parsed = parse_cloudinary_url(url)
    if not parsed or parsed["resource_type"] != "video":
        return None
    return delivery_url(url, fetch_format="jpg", width=640, crop="fill")
