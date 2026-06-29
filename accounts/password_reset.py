from django.core.cache import cache

from duo_project.email_utils import send_configured_mail

from .email_otp import OTP_TTL_SECONDS, generate_otp, normalize_email

PASSWORD_RESET_CACHE_PREFIX = "password_reset_otp:"


def _cache_key(email: str) -> str:
    return f"{PASSWORD_RESET_CACHE_PREFIX}{normalize_email(email)}"


def send_password_reset_otp(email: str) -> None:
    normalized = normalize_email(email)
    code = generate_otp()
    cache.set(_cache_key(normalized), code, OTP_TTL_SECONDS)

    send_configured_mail(
        subject="Reset your Duo password",
        message=(
            f"Your Duo password reset code is: {code}\n\n"
            "Enter this code in the app to set a new password. "
            "The code expires in 10 minutes.\n\n"
            "If you did not request this, you can ignore this email."
        ),
        recipient_list=[normalized],
    )


def verify_password_reset_otp(email: str, code: str) -> bool:
    normalized = normalize_email(email)
    stored = cache.get(_cache_key(normalized))
    if not stored or stored != code.strip():
        return False
    return True


def clear_password_reset_otp(email: str) -> None:
    cache.delete(_cache_key(normalize_email(email)))
