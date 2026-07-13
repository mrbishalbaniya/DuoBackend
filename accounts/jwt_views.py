import secrets

from django.core.cache import cache
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from duo_project.security.audit import log_security_event

from .auth_cookies import clear_auth_cookies, set_auth_cookies
from .security_serializers import DuoTokenObtainPairSerializer
from .throttling import AuthRateThrottle


class CookieTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [AuthRateThrottle]
    serializer_class = DuoTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as exc:
            detail = exc.detail
            if isinstance(detail, dict) and detail.get("requires_2fa"):
                challenge = detail.get("challenge_token", [None])[0]
                methods = detail.get("methods", [[]])[0]
                if isinstance(methods, str):
                    methods = [methods]
                return Response(
                    {
                        "requires_2fa": True,
                        "challenge_token": challenge,
                        "methods": methods or [],
                    },
                    status=status.HTTP_200_OK,
                )
            raise

        data = serializer.validated_data
        response = Response(data, status=status.HTTP_200_OK)
        set_auth_cookies(response, data["access"], data["refresh"])
        try:
            from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

            from security.services import security_service

            refresh_jti = str(RefreshToken(data["refresh"])["jti"])
            access_jti = str(AccessToken(data["access"])["jti"])
            security_service.register_access_token(access_jti, refresh_jti)
        except Exception:
            pass
        log_security_event("login_success", user_id=getattr(request.user, "id", None))
        return response


class CookieTokenRefreshView(TokenRefreshView):
    throttle_classes = [AuthRateThrottle]

    def post(self, request, *args, **kwargs):
        refresh = request.data.get("refresh") or request.COOKIES.get("duo_refresh")
        if not refresh:
            return Response({"detail": "Refresh token required."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            token = RefreshToken(refresh)
            jti = str(token["jti"])
        except TokenError:
            return Response({"detail": "Invalid refresh token."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            from security.services import security_service

            if not security_service.is_session_active(jti):
                log_security_event("refresh_denied_revoked", jti=jti)
                return Response({"detail": "Session revoked."}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception:
            log_security_event("refresh_session_check_failed", jti=jti)
            return Response({"detail": "Session validation failed."}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = self.get_serializer(data={"refresh": refresh})
        serializer.is_valid(raise_exception=True)
        access = serializer.validated_data["access"]
        new_refresh = serializer.validated_data.get("refresh", refresh)
        response = Response({"access": access}, status=status.HTTP_200_OK)
        set_auth_cookies(response, access, new_refresh)
        try:
            from rest_framework_simplejwt.tokens import AccessToken

            from security.services import security_service

            access_jti = str(AccessToken(access)["jti"])
            security_service.register_access_token(access_jti, jti)
            security_service.touch_session(jti)
        except Exception:
            pass
        return response


class LogoutView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from duo_project.security.tokens import revoke_access_token

        refresh = request.data.get("refresh") or request.COOKIES.get("duo_refresh")
        access = request.data.get("access") or request.COOKIES.get("duo_access")
        if access:
            revoke_access_token(access)
            try:
                from rest_framework_simplejwt.tokens import AccessToken

                from security.services import security_service

                security_service.revoke_access_session(str(AccessToken(access)["jti"]))
            except Exception:
                pass
        if refresh:
            try:
                from rest_framework_simplejwt.tokens import RefreshToken

                from security.models import UserSession

                token = RefreshToken(refresh)
                jti = str(token["jti"])
                session = UserSession.objects.filter(refresh_jti=jti).first()
                if session:
                    session.revoke()
                    log_security_event("logout_session_revoked", user_id=session.user_id, jti=jti)
                try:
                    token.blacklist()
                except Exception:
                    pass
            except Exception:
                log_security_event("logout_revoke_failed")
        response = Response({"detail": "Logged out."}, status=status.HTTP_200_OK)
        clear_auth_cookies(response)
        return response


class AuthHandoffCreateView(APIView):
    """Create a one-time handoff code for OAuth redirects (avoids tokens in URLs)."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        access = request.data.get("access")
        refresh = request.data.get("refresh")
        onboarded = request.data.get("onboarded", False)
        if not access or not refresh:
            return Response({"detail": "Missing tokens."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            RefreshToken(refresh)
        except TokenError:
            return Response({"detail": "Invalid tokens."}, status=status.HTTP_400_BAD_REQUEST)

        handoff_id = secrets.token_urlsafe(32)
        cache.set(
            f"auth_handoff:{handoff_id}",
            {"access": access, "refresh": refresh, "onboarded": bool(onboarded)},
            timeout=120,
        )
        return Response({"handoff": handoff_id})


class AuthHandoffExchangeView(APIView):
    """Exchange a one-time handoff code for auth cookies."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        handoff_id = request.data.get("handoff")
        if not handoff_id:
            return Response({"detail": "Missing handoff code."}, status=status.HTTP_400_BAD_REQUEST)

        cache_key = f"auth_handoff:{handoff_id}"
        payload = cache.get(cache_key)
        if not payload:
            return Response({"detail": "Invalid or expired handoff code."}, status=status.HTTP_400_BAD_REQUEST)

        cache.delete(cache_key)
        response = Response(
            {
                "access": payload["access"],
                "refresh": payload["refresh"],
                "onboarded": payload.get("onboarded", False),
            },
            status=status.HTTP_200_OK,
        )
        set_auth_cookies(response, payload["access"], payload["refresh"])
        return response
