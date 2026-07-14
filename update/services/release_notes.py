"""Sanitize OTA release notes for end-user display."""

from __future__ import annotations

import re
from typing import Iterable

DEFAULT_RELEASE_NOTES: list[str] = [
    "General performance improvements.",
    "Bug fixes.",
    "Improved stability.",
]

# Lines / phrases that must never reach mobile clients.
_BLOCKED_PATTERNS = re.compile(
    r"("
    r"\bcommit\b|"
    r"\bhash\b|"
    r"\bsha(?:-?256)?\b|"
    r"\bcertificate\b|"
    r"\bdigest\b|"
    r"\bapk\b|"
    r"\baab\b|"
    r"\bworkflow\b|"
    r"\bartifact\b|"
    r"\bgithub\b|"
    r"\brelease from\b|"
    r"\bsigning\b|"
    r"\binstall help\b|"
    r"\bpackage conflicts\b|"
    r"\bplay store\b|"
    r"\bdownload url\b|"
    r"\bchecksum\b|"
    r"\bmain\b\s*@|"
    r"[0-9a-f]{7,40}"  # commit-like hex
    r")",
    re.IGNORECASE,
)

_URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_MARKDOWN_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`]*)`")
_HEADING = re.compile(r"^#{1,6}\s*")
_BULLET = re.compile(r"^[-*+•]\s+")
_NUMBERED = re.compile(r"^\d+[.)]\s+")
_BOLD_ITALIC = re.compile(r"[*_~]+")
_WHITESPACE = re.compile(r"\s+")


def _strip_markdown(line: str) -> str:
    text = _MARKDOWN_FENCE.sub(" ", line)
    text = _INLINE_CODE.sub(r"\1", text)
    text = _HEADING.sub("", text)
    text = _BULLET.sub("", text)
    text = _NUMBERED.sub("", text)
    text = _BOLD_ITALIC.sub("", text)
    text = _URL_PATTERN.sub("", text)
    text = text.replace("|", " ")
    return _WHITESPACE.sub(" ", text).strip(" -\t")


def _is_blocked(line: str) -> bool:
    if not line:
        return True
    if _BLOCKED_PATTERNS.search(line):
        return True
    if any(token in line for token in ("```", "~~", "<", ">", "{", "}")):
        return True
    if len(line) < 8:
        return True
    return False


def _iter_raw_lines(raw) -> Iterable[str]:
    if raw is None:
        return
    if isinstance(raw, list):
        for item in raw:
            text = str(item).strip()
            if text:
                yield text
        return
    if isinstance(raw, str):
        cleaned = _MARKDOWN_FENCE.sub("\n", raw)
        for line in cleaned.splitlines():
            text = line.strip()
            if text:
                yield text


def sanitize_release_notes(
    raw,
    *,
    max_items: int = 12,
    with_fallback: bool = True,
) -> list[str]:
    """Return business-friendly bullet lines suitable for end users."""
    seen: set[str] = set()
    notes: list[str] = []

    for raw_line in _iter_raw_lines(raw):
        line = _strip_markdown(raw_line)
        if _is_blocked(line):
            continue
        if line and line[-1] not in ".!?":
            line = f"{line}."
        key = line.casefold()
        if key in seen:
            continue
        seen.add(key)
        notes.append(line)
        if len(notes) >= max_items:
            break

    if notes:
        return notes
    return list(DEFAULT_RELEASE_NOTES) if with_fallback else []


def parse_release_notes(raw) -> list[str]:
    """Normalize + filter notes for storage. Empty input stays empty."""
    return sanitize_release_notes(raw, with_fallback=False)


def resolve_release_title(title: str | None, *, version: str = "") -> str:
    cleaned = _strip_markdown((title or "").strip())
    if cleaned and not _is_blocked(cleaned) and len(cleaned) >= 4:
        return cleaned[:120]
    if version:
        return "Performance & Stability Update"
    return "App Update"
