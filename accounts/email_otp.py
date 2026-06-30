import random
import string

from django.core.cache import cache

from email_service.constants import EmailEvent
from email_service.service import send_email

OTP_TTL_SECONDS = 600
OTP_LENGTH = 6


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _cache_key(email: str) -> str:
    return f"email_otp:{normalize_email(email)}"


def generate_otp() -> str:
    return "".join(random.choices(string.digits, k=OTP_LENGTH))


def send_email_otp(email: str) -> None:
    normalized = normalize_email(email)
    code = generate_otp()
    cache.set(_cache_key(normalized), code, OTP_TTL_SECONDS)

    send_email(
        event=EmailEvent.REGISTRATION_OTP,
        to=normalized,
        context={
            "otp_code": code,
            "expiry_minutes": OTP_TTL_SECONDS // 60,
        },
        fail_silently=False,
    )


def verify_email_otp(email: str, code: str) -> bool:
    normalized = normalize_email(email)
    stored = cache.get(_cache_key(normalized))
    if not stored or stored != code.strip():
        return False
    cache.delete(_cache_key(normalized))
    return True
