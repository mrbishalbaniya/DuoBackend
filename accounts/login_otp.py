import secrets

from django.core.cache import cache

from email_service.constants import EmailEvent
from email_service.service import send_email

from .email_otp import (
    OTP_MAX_ATTEMPTS,
    OTP_TTL_SECONDS,
    generate_otp,
    get_otp_cooldown_remaining,
    normalize_email,
    start_otp_cooldown,
)

LOGIN_OTP_CACHE_PREFIX = "login_otp:"
LOGIN_OTP_ATTEMPTS_PREFIX = "login_otp_attempts:"
LOGIN_OTP_COOLDOWN_PREFIX = "login_otp_cooldown"


def _cache_key(email: str) -> str:
    return f"{LOGIN_OTP_CACHE_PREFIX}{normalize_email(email)}"


def _attempts_key(email: str) -> str:
    return f"{LOGIN_OTP_ATTEMPTS_PREFIX}{normalize_email(email)}"


def get_login_otp_cooldown_remaining(email: str) -> int:
    return get_otp_cooldown_remaining(LOGIN_OTP_COOLDOWN_PREFIX, email)


def start_login_otp_cooldown(email: str) -> None:
    start_otp_cooldown(LOGIN_OTP_COOLDOWN_PREFIX, email)


def send_login_otp(email: str) -> None:
    normalized = normalize_email(email)
    code = generate_otp()
    cache.set(_cache_key(normalized), code, OTP_TTL_SECONDS)
    cache.delete(_attempts_key(normalized))
    start_login_otp_cooldown(normalized)

    send_email(
        event=EmailEvent.LOGIN_VERIFICATION,
        to=normalized,
        context={
            "otp_code": code,
            "expiry_minutes": OTP_TTL_SECONDS // 60,
        },
        fail_silently=False,
        queue=True,
    )


def verify_login_otp(email: str, code: str) -> bool:
    normalized = normalize_email(email)
    attempts = int(cache.get(_attempts_key(normalized), 0))
    if attempts >= OTP_MAX_ATTEMPTS:
        cache.delete(_cache_key(normalized))
        return False

    stored = cache.get(_cache_key(normalized))
    if not stored or not secrets.compare_digest(stored, code.strip()):
        cache.set(_attempts_key(normalized), attempts + 1, OTP_TTL_SECONDS)
        return False

    cache.delete(_cache_key(normalized))
    cache.delete(_attempts_key(normalized))
    return True
