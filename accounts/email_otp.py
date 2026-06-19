import random
import string

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail

OTP_TTL_SECONDS = 600
OTP_LENGTH = 6


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _cache_key(email: str) -> str:
    return f"email_otp:{normalize_email(email)}"


def generate_otp() -> str:
    return "".join(random.choices(string.digits, k=OTP_LENGTH))


def send_email_otp(email: str) -> None:
    host_user = (settings.EMAIL_HOST_USER or "").strip()
    host_password = (settings.EMAIL_HOST_PASSWORD or "").replace(" ", "").strip()

    if not host_user or not host_password:
        raise ValueError(
            "Email OTP is not configured. Set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in .env."
        )

    normalized = normalize_email(email)
    code = generate_otp()
    cache.set(_cache_key(normalized), code, OTP_TTL_SECONDS)

    send_mail(
        subject="Your Duo verification code",
        message=(
            f"Your Duo verification code is: {code}\n\n"
            "Enter this code in the app to continue registration. "
            "The code expires in 10 minutes."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[normalized],
        fail_silently=False,
    )


def verify_email_otp(email: str, code: str) -> bool:
    normalized = normalize_email(email)
    stored = cache.get(_cache_key(normalized))
    if not stored or stored != code.strip():
        return False
    cache.delete(_cache_key(normalized))
    return True
