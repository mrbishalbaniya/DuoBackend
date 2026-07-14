"""Encrypt at-rest secrets for the security app (TOTP seeds, etc.)."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plain: str) -> str:
    if not plain:
        return ""
    if plain.startswith("enc:"):
        return plain
    token = _fernet().encrypt(plain.encode("utf-8")).decode("ascii")
    return f"enc:{token}"


def decrypt_secret(stored: str) -> str:
    if not stored:
        return ""
    if not stored.startswith("enc:"):
        # Legacy plaintext — still usable until next rotate/save.
        return stored
    try:
        return _fernet().decrypt(stored[4:].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""
