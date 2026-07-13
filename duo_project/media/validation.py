"""Upload validation — MIME, extension, size, security."""

from __future__ import annotations

import mimetypes
import os

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
VIDEO_TYPES = {"video/webm", "video/mp4", "video/quicktime"}
AUDIO_TYPES = {"audio/webm", "audio/ogg", "audio/mpeg", "audio/mp4", "audio/wav"}

MAX_PROFILE_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_CHAT_UPLOAD_BYTES = 25 * 1024 * 1024

BLOCKED_EXTENSIONS = {
    ".exe",
    ".bat",
    ".cmd",
    ".com",
    ".msi",
    ".dll",
    ".sh",
    ".php",
    ".js",
    ".html",
    ".htm",
    ".svg",
}


def guess_content_type(uploaded_file) -> str:
    content_type = getattr(uploaded_file, "content_type", None)
    if content_type:
        return content_type.split(";")[0].strip().lower()

    name = getattr(uploaded_file, "name", "") or ""
    guessed, _ = mimetypes.guess_type(name)
    return (guessed or "application/octet-stream").lower()


def safe_stem(filename: str) -> str:
    stem = os.path.splitext(os.path.basename(filename or "upload"))[0]
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem)
    return safe[:80] or "upload"


def validate_upload(uploaded_file, *, allowed_types: set[str], max_bytes: int) -> str:
    if not uploaded_file:
        raise ValueError("No file provided.")

    name = getattr(uploaded_file, "name", "") or ""
    ext = os.path.splitext(name)[1].lower()
    if ext in BLOCKED_EXTENSIONS:
        raise ValueError("Unsupported file type.")

    # Reject double extensions like photo.jpg.exe
    parts = name.lower().split(".")
    if len(parts) > 2 and f".{parts[-1]}" in BLOCKED_EXTENSIONS:
        raise ValueError("Unsupported file type.")

    size = getattr(uploaded_file, "size", None)
    if size is not None and size > max_bytes:
        raise ValueError(f"File is too large. Maximum size is {max_bytes // (1024 * 1024)} MB.")

    content_type = guess_content_type(uploaded_file)
    if content_type not in allowed_types:
        raise ValueError("Unsupported file type.")

    validate_file_signature(uploaded_file, content_type)

    if ".." in name or name.startswith("/") or name.startswith("\\"):
        raise ValueError("Invalid filename.")

    return content_type


# Magic-byte signatures for common upload types (first bytes).
_FILE_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),  # followed by WEBP at offset 8
    "audio/mpeg": (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"),
    "audio/ogg": (b"OggS",),
    "audio/wav": (b"RIFF",),
    "video/mp4": (b"\x00\x00\x00",),  # ftyp at offset 4
    "video/webm": (b"\x1a\x45\xdf\xa3",),
}


def _matches_signature(header: bytes, content_type: str) -> bool:
    sigs = _FILE_SIGNATURES.get(content_type)
    if not sigs:
        return True
    if content_type == "image/webp":
        return header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WEBP"
    if content_type == "video/mp4":
        return len(header) >= 8 and header[4:8] == b"ftyp"
    if content_type == "audio/wav":
        return header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WAVE"
    return any(header.startswith(sig) for sig in sigs)


def validate_file_signature(uploaded_file, content_type: str) -> None:
    """Reject files whose content does not match declared MIME type."""
    uploaded_file.seek(0)
    header = uploaded_file.read(32)
    uploaded_file.seek(0)
    if not header:
        raise ValueError("Empty file.")
    if not _matches_signature(header, content_type):
        raise ValueError("File content does not match declared type.")


def validate_image_dimensions(
    uploaded_file,
    *,
    min_width: int = 200,
    min_height: int = 200,
    max_width: int = 8000,
    max_height: int = 8000,
) -> None:
    """Reject corrupted or out-of-range images when Pillow is available."""
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError:
        return

    uploaded_file.seek(0)
    try:
        with Image.open(uploaded_file) as img:
            width, height = img.size
            img.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Invalid or corrupted image file.") from exc
    finally:
        uploaded_file.seek(0)

    if width < min_width or height < min_height:
        raise ValueError(
            f"Image is too small. Minimum size is {min_width}x{min_height} pixels."
        )
    if width > max_width or height > max_height:
        raise ValueError(
            f"Image dimensions exceed maximum of {max_width}x{max_height} pixels."
        )


def is_image_type(content_type: str) -> bool:
    return content_type.startswith("image/")


def is_video_type(content_type: str) -> bool:
    return content_type in VIDEO_TYPES


def is_audio_type(content_type: str) -> bool:
    return content_type in AUDIO_TYPES
