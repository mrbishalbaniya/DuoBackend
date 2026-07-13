"""Upload response payload helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MediaUploadResponse:
    image_url: str
    media: dict[str, Any] | None = None


def upload_response_dict(result: MediaUploadResponse) -> dict[str, Any]:
    payload: dict[str, Any] = {"image_url": result.image_url}
    if result.media:
        payload["media"] = result.media
    return payload
