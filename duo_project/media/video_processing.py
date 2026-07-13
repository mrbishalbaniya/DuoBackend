"""Video thumbnail generation (optional, uses OpenCV when available)."""

from __future__ import annotations

import io
import logging
import tempfile

from PIL import Image

logger = logging.getLogger("duo.media")


def extract_video_thumbnail(file_obj) -> bytes | None:
    try:
        import cv2  # noqa: WPS433 — optional runtime dependency
    except ImportError:
        return None

    try:
        file_obj.seek(0)
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=True) as tmp:
            tmp.write(file_obj.read())
            tmp.flush()
            cap = cv2.VideoCapture(tmp.name)
            ok, frame = cap.read()
            cap.release()
            if not ok or frame is None:
                return None
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame_rgb)
            image.thumbnail((640, 640), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="WEBP", quality=80)
            return buffer.getvalue()
    except Exception as exc:
        logger.debug("video_thumbnail_failed error=%s", exc)
        return None
