import random
import string

from django.core.cache import cache

from duo_project.email_utils import send_configured_mail

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

    send_configured_mail(
        subject="Your Duo verification code",
        message=(
            f"Your Duo verification code is: {code}\n\n"
            "Enter this code in the app to continue registration. "
            "The code expires in 10 minutes."
        ),
        recipient_list=[normalized],
    )


def verify_email_otp(email: str, code: str) -> bool:
    normalized = normalize_email(email)
    stored = cache.get(_cache_key(normalized))
    if not stored or stored != code.strip():
        return False
    cache.delete(_cache_key(normalized))
    return True
