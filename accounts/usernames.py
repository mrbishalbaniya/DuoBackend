"""Username generation and validation shared by sign-up and the account page."""
import re
import secrets
import unicodedata

from django.contrib.auth import get_user_model
from rest_framework import serializers

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 30
USERNAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._]*[a-z0-9])?$")


def _slugify_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    parts = re.findall(r"[a-z0-9]+", ascii_name.lower())
    return ".".join(parts)[:20].strip(".")


def generate_username(name: str = "", email: str = "") -> str:
    """Build a unique random username from a person's name, like ``bishal.baniya4821``."""
    User = get_user_model()
    base = _slugify_name(name)
    if not base and email:
        base = _slugify_name(email.split("@")[0].replace(".", " "))
    if len(base) < 2:
        base = "duo.user"
    for _ in range(50):
        candidate = f"{base}{secrets.randbelow(9000) + 1000}"
        if not User.objects.filter(username__iexact=candidate).exists():
            return candidate
    return f"{base}{secrets.token_hex(4)}"


def validate_username(value: str, *, exclude_user_id=None) -> str:
    """Normalise and check a username a person chose; raises ValidationError."""
    username = (value or "").strip().lstrip("@").lower()
    if not (USERNAME_MIN_LENGTH <= len(username) <= USERNAME_MAX_LENGTH):
        raise serializers.ValidationError(
            f"Username must be {USERNAME_MIN_LENGTH}-{USERNAME_MAX_LENGTH} characters."
        )
    if not USERNAME_PATTERN.match(username) or ".." in username:
        raise serializers.ValidationError(
            "Use only lowercase letters, numbers, dots and underscores, "
            "starting and ending with a letter or number."
        )
    User = get_user_model()
    taken = User.objects.filter(username__iexact=username)
    if exclude_user_id is not None:
        taken = taken.exclude(pk=exclude_user_id)
    if taken.exists():
        raise serializers.ValidationError("That username is already taken.")
    return username
