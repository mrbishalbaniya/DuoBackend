"""JWT authentication from Authorization header or httpOnly cookie."""

from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """Accept Bearer tokens or the `duo_access` httpOnly cookie."""

    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:
            raw_token = self.get_raw_token(header)
            if raw_token is not None:
                validated = self.get_validated_token(raw_token)
                return self.get_user(validated), validated

        cookie_token = request.COOKIES.get("duo_access")
        if not cookie_token:
            return None

        try:
            validated = self.get_validated_token(cookie_token)
        except Exception:
            return None

        return self.get_user(validated), validated
