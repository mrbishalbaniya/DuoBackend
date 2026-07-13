"""Validate email provider credentials without logging secrets."""

from __future__ import annotations

PLACEHOLDER_MARKERS = (
    "your-brevo",
    "your-brevo-smtp",
    "xkeysib-your",
    "xsmtpsib-your",
    "change-me",
    "example.com",
    "placeholder",
)


def is_placeholder(value: str) -> bool:
    text = (value or "").strip().lower()
    if not text:
        return True
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def is_valid_brevo_api_key(value: str) -> bool:
    key = (value or "").strip()
    return key.startswith("xkeysib-") and len(key) > 20 and not is_placeholder(key)


def is_valid_brevo_smtp_key(value: str) -> bool:
    key = (value or "").strip().replace(" ", "")
    return key.startswith("xsmtpsib-") and len(key) > 20 and not is_placeholder(key)


def is_valid_resend_api_key(value: str) -> bool:
    key = (value or "").strip()
    return key.startswith("re_") and len(key) > 10 and not is_placeholder(key)


def smtp_configured(host: str, username: str, password: str) -> bool:
    host_value = (host or "").strip()
    user = (username or "").strip()
    pwd = (password or "").strip().replace(" ", "")
    if not host_value or not user or not pwd:
        return False
    if is_placeholder(pwd) or pwd.startswith("enc:"):
        return False
    return True
