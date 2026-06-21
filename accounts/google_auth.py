from django.conf import settings
from django.contrib.auth import get_user_model
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from .models import Profile

User = get_user_model()


def verify_google_id_token(token: str) -> dict:
    client_id = settings.GOOGLE_OAUTH_CLIENT_ID
    if not client_id:
        raise ValueError("Google OAuth is not configured.")

    idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), client_id)

    issuer = idinfo.get("iss")
    if issuer not in ("accounts.google.com", "https://accounts.google.com"):
        raise ValueError("Invalid token issuer.")

    if not idinfo.get("email_verified", False):
        raise ValueError("Google email is not verified.")

    email = idinfo.get("email")
    if not email:
        raise ValueError("Google account has no email address.")

    return idinfo


def get_or_create_google_user(idinfo: dict):
    email = idinfo["email"].strip().lower()
    full_name = (idinfo.get("name") or "").strip()
    first_name = (idinfo.get("given_name") or "").strip()
    last_name = (idinfo.get("family_name") or "").strip()

    user = User.objects.filter(email__iexact=email).order_by("id").first()
    created = False

    if user is None:
        username = email
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1

        user = User.objects.create(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])
        created = True
    elif not user.first_name and first_name:
        user.first_name = first_name
        user.last_name = last_name
        user.save(update_fields=["first_name", "last_name"])

    profile, profile_created = Profile.objects.get_or_create(user=user)
    if profile_created or not profile.full_name:
        profile.full_name = full_name or f"{first_name} {last_name}".strip() or email.split("@")[0]
        profile.save(update_fields=["full_name"])

    return user, created
