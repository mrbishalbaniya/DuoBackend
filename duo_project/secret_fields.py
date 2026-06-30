"""Encrypt/decrypt sensitive values stored in the database."""

from __future__ import annotations

import base64
import hashlib
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_PREFIX = "enc:"


def _fernet():
    from cryptography.fernet import Fernet

    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plain: str) -> str:
    if not plain or plain.startswith(_PREFIX):
        return plain
    token = _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")
    return f"{_PREFIX}{token}"


def decrypt_secret(stored: str) -> str:
    if not stored:
        return ""
    if not stored.startswith(_PREFIX):
        return stored
    try:
        token = stored[len(_PREFIX) :]
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception:
        logger.warning("Failed to decrypt stored secret; treating as plaintext")
        return stored[len(_PREFIX) :]


def mask_secret(value: str, visible: int = 4) -> str:
    if not value:
        return ""
    if value.startswith(_PREFIX):
        return "••••••••"
    if len(value) <= visible:
        return "•" * len(value)
    return ("•" * (len(value) - visible)) + value[-visible:]
