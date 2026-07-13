import secrets

from django.core.cache import cache

from email_service.constants import EmailEvent
from email_service.service import send_email

from .email_otp import OTP_MAX_ATTEMPTS, OTP_TTL_SECONDS, generate_otp, normalize_email

PASSWORD_RESET_CACHE_PREFIX = "password_reset_otp:"
PASSWORD_RESET_ATTEMPTS_PREFIX = "password_reset_attempts:"


def _cache_key(email: str) -> str:
    return f"{PASSWORD_RESET_CACHE_PREFIX}{normalize_email(email)}"


def _attempts_key(email: str) -> str:
    return f"{PASSWORD_RESET_ATTEMPTS_PREFIX}{normalize_email(email)}"


def send_password_reset_otp(email: str) -> None:
    normalized = normalize_email(email)
    code = generate_otp()
    cache.set(_cache_key(normalized), code, OTP_TTL_SECONDS)
    cache.delete(_attempts_key(normalized))

    send_email(
        event=EmailEvent.PASSWORD_RESET_OTP,
        to=normalized,
        context={
            "otp_code": code,
            "expiry_minutes": OTP_TTL_SECONDS // 60,
        },
        fail_silently=False,
        queue=True,
    )


def verify_password_reset_otp(email: str, code: str) -> bool:
    normalized = normalize_email(email)
    attempts = int(cache.get(_attempts_key(normalized), 0))
    if attempts >= OTP_MAX_ATTEMPTS:
        cache.delete(_cache_key(normalized))
        return False

    stored = cache.get(_cache_key(normalized))
    if not stored or not secrets.compare_digest(stored, code.strip()):
        cache.set(_attempts_key(normalized), attempts + 1, OTP_TTL_SECONDS)
        return False
    return True


def clear_password_reset_otp(email: str) -> None:
    cache.delete(_cache_key(normalize_email(email)))
    cache.delete(_attempts_key(normalize_email(email)))
