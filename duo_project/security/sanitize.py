"""Input sanitization helpers for user-controlled text."""

from __future__ import annotations

import re
import unicodedata

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HTML_TAG = re.compile(r"<[^>]+>")
_MAX_TEXT_LEN = 10_000


def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def strip_control_characters(text: str) -> str:
    return _CONTROL_CHARS.sub("", text)


def strip_html_tags(text: str) -> str:
    return _HTML_TAG.sub("", text)


def sanitize_plain_text(
    value: str | None,
    *,
    max_length: int = _MAX_TEXT_LEN,
    allow_newlines: bool = True,
) -> str:
    """Normalize, trim, and strip dangerous characters from plain text."""
    if value is None:
        return ""
    text = normalize_unicode(str(value)).strip()
    text = strip_control_characters(text)
    text = strip_html_tags(text)
    if not allow_newlines:
        text = text.replace("\n", " ").replace("\r", " ")
    if len(text) > max_length:
        text = text[:max_length]
    return text


def sanitize_filename(filename: str, *, max_length: int = 200) -> str:
    name = normalize_unicode(filename or "").strip()
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^\w.\- ]", "_", name)
    return name[:max_length] or "upload"
