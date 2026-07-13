"""Access-token revocation helpers (logout / session kill)."""

from __future__ import annotations

from django.conf import settings
from django.core.cache import cache

_ACCESS_REVOKE_PREFIX = "revoked_access:"


def _revoke_ttl() -> int:
    lifetime = getattr(settings, "SIMPLE_JWT", {}).get("ACCESS_TOKEN_LIFETIME", 3600)
    return int(lifetime.total_seconds()) if hasattr(lifetime, "total_seconds") else int(lifetime)


def revoke_access_token(access_token: str) -> None:
    """Mark an access JWT as revoked until its natural expiry."""
    if not access_token:
        return
    try:
        from rest_framework_simplejwt.tokens import AccessToken

        token = AccessToken(access_token)
        jti = str(token.get("jti", ""))
        if jti:
            cache.set(f"{_ACCESS_REVOKE_PREFIX}{jti}", True, timeout=_revoke_ttl())
    except Exception:
        pass


def is_access_token_revoked(access_token: str) -> bool:
    if not access_token:
        return False
    try:
        from rest_framework_simplejwt.tokens import AccessToken

        token = AccessToken(access_token)
        jti = str(token.get("jti", ""))
        if not jti:
            return False
        return bool(cache.get(f"{_ACCESS_REVOKE_PREFIX}{jti}"))
    except Exception:
        return False
