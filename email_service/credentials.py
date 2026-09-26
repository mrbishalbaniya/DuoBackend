"""Validate email provider credentials without logging secrets."""

from __future__ import annotations

PLACEHOLDER_MARKERS = (
    "change-me",
    "example.com",
    "placeholder",
)


def is_placeholder(value: str) -> bool:
    text = (value or "").strip().lower()
    if not text:
        return True
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def smtp_configured(host: str, username: str, password: str) -> bool:
    host_value = (host or "").strip()
    user = (username or "").strip()
    pwd = (password or "").strip().replace(" ", "")
    if not host_value or not user or not pwd:
        return False
    if is_placeholder(pwd) or pwd.startswith("enc:"):
        return False
    return True
