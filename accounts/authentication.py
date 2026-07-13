"""JWT authentication from Authorization header or httpOnly cookie."""

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from duo_project.security.tokens import is_access_token_revoked


class CookieJWTAuthentication(JWTAuthentication):
    """Accept Bearer tokens or the `duo_access` httpOnly cookie."""

    def authenticate(self, request):
        header = self.get_header(request)
        raw_token = None

        if header is not None:
            raw_token = self.get_raw_token(header)

        cookie_token = request.COOKIES.get("duo_access")
        if raw_token is None and cookie_token:
            raw_token = cookie_token.encode("utf-8")

        if raw_token is None:
            return None

        token_str = raw_token.decode("utf-8") if isinstance(raw_token, bytes) else str(raw_token)
        if is_access_token_revoked(token_str):
            raise AuthenticationFailed("Token has been revoked.")

        try:
            validated = self.get_validated_token(raw_token)
        except Exception:
            return None

        user = self.get_user(validated)

        # Session revocation: access tokens must map to an active refresh session.
        try:
            from security.services import security_service

            jti = str(validated.get("jti", ""))
            if jti and not security_service.is_access_session_active(jti):
                raise AuthenticationFailed("Session has been revoked.")
        except AuthenticationFailed:
            raise
        except Exception:
            pass

        return user, validated
