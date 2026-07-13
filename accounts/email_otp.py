import secrets
import string

from django.conf import settings
from django.core.cache import cache

from email_service.constants import EmailEvent
from email_service.service import send_email

OTP_TTL_SECONDS = 600
OTP_LENGTH = 6
OTP_MAX_ATTEMPTS = 5
EMAIL_VERIFIED_TTL_SECONDS = 1800
EMAIL_VERIFIED_PREFIX = "email_verified:"
OTP_ATTEMPTS_PREFIX = "email_otp_attempts:"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _cache_key(email: str) -> str:
    return f"email_otp:{normalize_email(email)}"


def _attempts_key(email: str) -> str:
    return f"{OTP_ATTEMPTS_PREFIX}{normalize_email(email)}"


def _verified_key(email: str) -> str:
    return f"{EMAIL_VERIFIED_PREFIX}{normalize_email(email)}"


def generate_otp() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(OTP_LENGTH))


def require_email_otp_for_registration() -> bool:
    return settings.REQUIRE_EMAIL_OTP_FOR_REGISTRATION


def mark_email_verified(email: str) -> None:
    cache.set(_verified_key(email), True, EMAIL_VERIFIED_TTL_SECONDS)


def is_email_verified_for_registration(email: str) -> bool:
    if not require_email_otp_for_registration():
        return True
    return bool(cache.get(_verified_key(email)))


def clear_email_verified(email: str) -> None:
    cache.delete(_verified_key(email))


def send_email_otp(email: str) -> None:
    normalized = normalize_email(email)
    code = generate_otp()
    cache.set(_cache_key(normalized), code, OTP_TTL_SECONDS)
    cache.delete(_attempts_key(normalized))

    send_email(
        event=EmailEvent.REGISTRATION_OTP,
        to=normalized,
        context={
            "otp_code": code,
            "expiry_minutes": OTP_TTL_SECONDS // 60,
        },
        fail_silently=False,
        queue=True,
    )


def verify_email_otp(email: str, code: str) -> bool:
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
    mark_email_verified(normalized)
    return True
