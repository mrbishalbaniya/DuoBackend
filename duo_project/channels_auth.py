"""JWT authentication middleware for Django Channels WebSocket connections."""

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
WS_TICKET_MAX_AGE = 60


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


def _user_from_ws_ticket(ticket: str, conversation_id: str):
    signer = TimestampSigner(salt=WS_TICKET_SALT)
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


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        if scope["type"] != "websocket":
            return await super().__call__(scope, receive, send)

        scope = dict(scope)
        conversation_id = scope["url_route"]["kwargs"].get("conversation_id")
        query_string = scope.get("query_string", b"").decode()
        query = parse_qs(query_string)

        user_id = None
        if query.get("ticket") and conversation_id is not None:
            user_id = _user_from_ws_ticket(query["ticket"][0], str(conversation_id))
        else:
            token = _extract_token(scope)
            if token:
                user_id = _user_from_access_token(token)

        if user_id:
            scope["user"] = await _get_user(user_id)
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)
