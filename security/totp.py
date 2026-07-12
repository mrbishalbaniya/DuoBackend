import base64
import hashlib
import hmac
import secrets
import struct
import time

from django.conf import settings


def generate_totp_secret() -> str:
    raw = secrets.token_bytes(20)
    return base64.b32encode(raw).decode("utf-8").rstrip("=")


def build_otpauth_uri(*, secret: str, email: str, issuer: str = "Duo") -> str:
    from urllib.parse import quote

    label = quote(f"{issuer}:{email}")
    issuer_q = quote(issuer)
    return f"otpauth://totp/{label}?secret={secret}&issuer={issuer_q}&algorithm=SHA1&digits=6&period=30"


def _hotp(secret_b32: str, counter: int) -> str:
    padding = "=" * ((8 - len(secret_b32) % 8) % 8)
    key = base64.b32decode(secret_b32.upper() + padding)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % 1_000_000).zfill(6)


def verify_totp(secret: str, code: str, *, window: int = 1) -> bool:
    if not secret or not code:
        return False
    normalized = code.strip().replace(" ", "")
    if len(normalized) != 6 or not normalized.isdigit():
        return False
    counter = int(time.time()) // 30
    for offset in range(-window, window + 1):
        if hmac.compare_digest(_hotp(secret, counter + offset), normalized):
            return True
    return False


def current_totp(secret: str) -> str:
    counter = int(time.time()) // 30
    return _hotp(secret, counter)
