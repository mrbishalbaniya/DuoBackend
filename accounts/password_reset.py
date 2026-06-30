from django.core.cache import cache

from email_service.constants import EmailEvent
from email_service.service import send_email

from .email_otp import OTP_TTL_SECONDS, generate_otp, normalize_email

PASSWORD_RESET_CACHE_PREFIX = "password_reset_otp:"


def _cache_key(email: str) -> str:
    return f"{PASSWORD_RESET_CACHE_PREFIX}{normalize_email(email)}"


def send_password_reset_otp(email: str) -> None:
    normalized = normalize_email(email)
    code = generate_otp()
    cache.set(_cache_key(normalized), code, OTP_TTL_SECONDS)

    send_email(
        event=EmailEvent.PASSWORD_RESET_OTP,
        to=normalized,
        context={
            "otp_code": code,
            "expiry_minutes": OTP_TTL_SECONDS // 60,
        },
        fail_silently=False,
    )


def verify_password_reset_otp(email: str, code: str) -> bool:
    normalized = normalize_email(email)
    stored = cache.get(_cache_key(normalized))
    if not stored or stored != code.strip():
        return False
    return True


def clear_password_reset_otp(email: str) -> None:
    cache.delete(_cache_key(normalize_email(email)))
