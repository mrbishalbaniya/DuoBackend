from django.conf import settings
from django.contrib.auth import get_user_model

from .firebase_auth import normalize_phone, verify_firebase_id_token
from .models import Profile

User = get_user_model()


def verify_firebase_phone_token(id_token: str, expected_phone: str | None = None) -> str:
    decoded = verify_firebase_id_token(id_token)
    phone = decoded.get("phone_number")
    if not phone:
        raise ValueError("Firebase token does not include a verified phone number.")

    if expected_phone and normalize_phone(phone) != normalize_phone(expected_phone):
        raise ValueError("Verified phone number does not match the submitted number.")

    return phone


def get_or_create_phone_user(phone: str):
    digits = normalize_phone(phone).lstrip("+")
    email = f"phone_{digits}@duo.app"
    username = email

    user, created = User.objects.get_or_create(
        email=email,
        defaults={"username": username},
    )

    if created:
        user.set_unusable_password()
        user.save()

    phone_parts = _split_e164(phone)
    profile, profile_created = Profile.objects.get_or_create(user=user)
    if phone_parts:
        country_code, national = phone_parts
        profile.phone_country_code = country_code
        profile.phone_number = national
        profile.save(update_fields=["phone_country_code", "phone_number", "updated_at"])

    return user, created


def _split_e164(phone: str) -> tuple[str, str] | None:
    normalized = normalize_phone(phone)
    if not normalized.startswith("+") or len(normalized) < 5:
        return None

    if normalized.startswith("+977"):
        return "+977", normalized[4:]

    return normalized[:4], normalized[4:]
