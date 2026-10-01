"""JWT authentication middleware for Django Channels WebSocket connections."""

import re
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
WS_TICKET_SALT = "duo-ws-ticket"
CALL_WS_TICKET_SALT = "duo-call-ws-ticket"
INBOX_WS_TICKET_SALT = "duo-inbox-ws-ticket"
WS_TICKET_MAX_AGE = 300

# JWTAuthMiddleware wraps URLRouter (see asgi.py), so it runs BEFORE routing —
# scope["url_route"] is populated by URLRouter itself when it dispatches to the
# matched consumer, and is never visible to an outer middleware. conversation_id
# must therefore be parsed straight from the raw path, not from url_route kwargs.
_CONVERSATION_PATH_RE = re.compile(r"/ws/(?:chat|call)/(?P<conversation_id>[^/?]+)/?")


def _conversation_id_from_path(path: str) -> str | None:
    match = _CONVERSATION_PATH_RE.search(path or "")
    return match.group("conversation_id") if match else None


@database_sync_to_async
def _get_user(user_id: int):
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()


def _user_from_access_token(token: str):
    try:
        validated = AccessToken(token)
        return validated["user_id"]
    except (InvalidToken, TokenError, KeyError):
        return None


def _user_from_inbox_ws_ticket(ticket: str):
    signer = TimestampSigner(salt=INBOX_WS_TICKET_SALT)
    try:
        payload = signer.unsign(ticket, max_age=WS_TICKET_MAX_AGE)
        return int(payload)
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None


def _user_from_ws_ticket(ticket: str, conversation_id: str, *, salt: str = WS_TICKET_SALT):
    signer = TimestampSigner(salt=salt)
    try:
        payload = signer.unsign(ticket, max_age=WS_TICKET_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None

    try:
        user_id_str, convo_id_str = payload.split(":", 1)
        if convo_id_str != str(conversation_id):
            return None
        return int(user_id_str)
    except (TypeError, ValueError):
        return None


def _extract_token(scope) -> str | None:
    query_string = scope.get("query_string", b"").decode()
    query = parse_qs(query_string)

    if query.get("ticket"):
        return None  # handled separately

    if query.get("token"):
        return query["token"][0]

    for header_name, header_value in scope.get("headers", []):
        if header_name.lower() == b"authorization":
            value = header_value.decode()
            if value.lower().startswith("bearer "):
                return value[7:].strip()

    cookie_header = ""
    for header_name, header_value in scope.get("headers", []):
        if header_name.lower() == b"cookie":
            cookie_header = header_value.decode()
            break

    if cookie_header:
        for part in cookie_header.split(";"):
            part = part.strip()
            if part.startswith("duo_access="):
                return part.split("=", 1)[1]

    return None


# Staff-only sockets used from Django admin pages, which have a session but no JWT.
SESSION_WS_PATHS = ("/ws/analytics/",)


def _header(scope, name: bytes) -> str:
    for header_name, header_value in scope.get("headers", []):
        if header_name.lower() == name:
            return header_value.decode("latin-1")
    return ""


def _same_origin(scope) -> bool:
    """Reject cross-site WebSocket hijacking: Origin must match Host."""
    origin = _header(scope, b"origin")
    host = _header(scope, b"host")
    if not origin or not host:
        return False
    return origin.split("://", 1)[-1].rstrip("/").lower() == host.lower()


@database_sync_to_async
def _user_from_session(scope):
    from importlib import import_module

    from django.conf import settings
    from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
    from django.utils.crypto import constant_time_compare

    session_key = None
    for part in _header(scope, b"cookie").split(";"):
        name, _, value = part.strip().partition("=")
        if name == settings.SESSION_COOKIE_NAME:
            session_key = value
            break
    if not session_key:
        return AnonymousUser()

    session = import_module(settings.SESSION_ENGINE).SessionStore(session_key=session_key)
    user_id = session.get(SESSION_KEY)
    if not user_id or session.get(BACKEND_SESSION_KEY) not in settings.AUTHENTICATION_BACKENDS:
        return AnonymousUser()
    try:
        user = User.objects.get(pk=user_id)
    except (User.DoesNotExist, ValueError):
        return AnonymousUser()
    # Same check Django's auth.get_user does: a password change ends the session.
    if not constant_time_compare(session.get(HASH_SESSION_KEY, ""), user.get_session_auth_hash()):
        return AnonymousUser()
    if not user.is_active:
        return AnonymousUser()
    return user


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        if scope["type"] != "websocket":
            return await super().__call__(scope, receive, send)

        scope = dict(scope)
        path = scope.get("path", "")
        url_route = scope.get("url_route", {})
        kwargs = url_route.get("kwargs", {}) if url_route else {}
        conversation_id = kwargs.get("conversation_id") or _conversation_id_from_path(path)
        query_string = scope.get("query_string", b"").decode()
        query = parse_qs(query_string)

        # Admin-page sockets: an admin session wins over any app JWT cookie that
        # the browser also sends for a different user on the same host.
        if path.startswith(SESSION_WS_PATHS) and _same_origin(scope):
            session_user = await _user_from_session(scope)
            if session_user.is_authenticated:
                scope["user"] = session_user
                return await super().__call__(scope, receive, send)

        user_id = None
        ticket_salt = CALL_WS_TICKET_SALT if "/ws/call/" in path else WS_TICKET_SALT
        if query.get("ticket") and "/ws/inbox/" in path:
            user_id = _user_from_inbox_ws_ticket(query["ticket"][0])
        elif query.get("ticket") and conversation_id is not None:
            user_id = _user_from_ws_ticket(
                query["ticket"][0],
                str(conversation_id),
                salt=ticket_salt,
            )
        else:
            token = _extract_token(scope)
            if token:
                user_id = _user_from_access_token(token)

        if user_id:
            scope["user"] = await _get_user(user_id)
        elif path.startswith(SESSION_WS_PATHS) and _same_origin(scope):
            # Admin pages authenticate with a Django session, not a JWT.
            scope["user"] = await _user_from_session(scope)
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)
