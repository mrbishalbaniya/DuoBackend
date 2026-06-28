"""Helpers for setting and clearing JWT auth cookies."""

from django.conf import settings
from django.http import HttpResponse


ACCESS_COOKIE = "duo_access"
REFRESH_COOKIE = "duo_refresh"


def _cookie_kwargs(max_age: int) -> dict:
    secure = not settings.DEBUG
    return {
        "max_age": max_age,
        "httponly": True,
        "secure": secure,
        "samesite": "None" if secure else "Lax",
        "path": "/",
    }


def set_auth_cookies(response: HttpResponse, access: str, refresh: str) -> HttpResponse:
    access_lifetime = int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())
    refresh_lifetime = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
    response.set_cookie(ACCESS_COOKIE, access, **_cookie_kwargs(access_lifetime))
    response.set_cookie(REFRESH_COOKIE, refresh, **_cookie_kwargs(refresh_lifetime))
    return response


def clear_auth_cookies(response: HttpResponse) -> HttpResponse:
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.delete_cookie(name, path="/", samesite="None" if not settings.DEBUG else "Lax")
    return response
