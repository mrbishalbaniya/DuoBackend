from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema

from accounts.auth_cookies import set_auth_cookies
from accounts.throttling import AuthRateThrottle

from .serializers import (
    BackupCodesResponseSerializer,
    BiometricEnableSerializer,
    BiometricLoginSerializer,
    BiometricStatusSerializer,
    DeviceRenameSerializer,
    LoginHistorySerializer,
    LogoutAllSerializer,
    PasswordVerifySerializer,
    SecurityEventSerializer,
    SecurityOverviewSerializer,
    TwoFactorEnableResponseSerializer,
    TwoFactorLoginChallengeSerializer,
    TwoFactorMethodChoiceSerializer,
    TwoFactorSetupTotpResponseSerializer,
    TwoFactorVerifySerializer,
    UserDeviceSerializer,
)
from .services import security_service
from duo_project.cache import api_cache, get_user_cache_version
from duo_project.cache.invalidation import invalidate_user_caches
from duo_project.cache import keys as cache_keys
from duo_project.cache import ttl as cache_ttl


def _current_jti(request) -> str:
    refresh = request.data.get("refresh_token") or request.COOKIES.get("duo_refresh", "")
    if not refresh:
        return ""
    try:
        return str(RefreshToken(refresh)["jti"])
    except Exception:
        return ""


def _current_device_id(request) -> str:
    return (request.data.get("device_id") or request.headers.get("X-Device-Id") or "").strip()


class SecurityOverviewView(APIView):
    @extend_schema(tags=["Security"], summary="Security center overview", responses={200: SecurityOverviewSerializer})
    def get(self, request):
        data = security_service.overview(
            request.user,
            current_device_id=_current_device_id(request),
            current_jti=_current_jti(request),
        )
        return Response(SecurityOverviewSerializer(data).data)


class PasswordVerifyView(APIView):
    @extend_schema(tags=["Security"], summary="Verify account password")
    def post(self, request):
        serializer = PasswordVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ok = security_service.verify_password(request.user, serializer.validated_data["password"])
        if not ok:
            return Response({"verified": False, "detail": "Incorrect password."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"verified": True})


class TwoFactorSetupTotpView(APIView):
    @extend_schema(tags=["Security"], summary="Generate TOTP secret", responses={200: TwoFactorSetupTotpResponseSerializer})
    def post(self, request):
        serializer = PasswordVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not security_service.verify_password(request.user, serializer.validated_data["password"]):
            return Response({"detail": "Incorrect password."}, status=status.HTTP_400_BAD_REQUEST)
        data = security_service.setup_totp(request.user)
        return Response(data)


class TwoFactorSetupEmailView(APIView):
    @extend_schema(tags=["Security"], summary="Send email OTP for 2FA setup")
    def post(self, request):
        serializer = PasswordVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not security_service.verify_password(request.user, serializer.validated_data["password"]):
            return Response({"detail": "Incorrect password."}, status=status.HTTP_400_BAD_REQUEST)
        security_service.send_2fa_email_otp(request.user)
        return Response({"sent": True, "message": "Verification code sent to your email."})


class TwoFactorEnableView(APIView):
    @extend_schema(tags=["Security"], summary="Verify code and enable 2FA", responses={200: TwoFactorEnableResponseSerializer})
    def post(self, request):
        serializer = TwoFactorVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            codes = security_service.verify_and_enable_2fa(
                request.user, serializer.validated_data["code"]
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"enabled": True, "backup_codes": codes})


class TwoFactorDisableView(APIView):
    @extend_schema(tags=["Security"], summary="Disable 2FA")
    def post(self, request):
        serializer = PasswordVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            security_service.disable_2fa(request.user, serializer.validated_data["password"])
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"disabled": True})


class BackupCodesRegenerateView(APIView):
    @extend_schema(tags=["Security"], summary="Regenerate backup codes", responses={200: BackupCodesResponseSerializer})
    def post(self, request):
        serializer = PasswordVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            codes = security_service.regenerate_backup_codes(
                request.user, serializer.validated_data["password"]
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            "codes": codes,
            "remaining": len(codes),
        })


class BackupCodesStatusView(APIView):
    @extend_schema(tags=["Security"], summary="Remaining backup codes count")
    def get(self, request):
        remaining = security_service.remaining_backup_codes(request.user)
        return Response({"remaining": remaining})


class TwoFactorLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    @extend_schema(tags=["Security"], summary="Complete login with 2FA code")
    def post(self, request):
        serializer = TwoFactorLoginChallengeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = security_service.complete_login_challenge(
                serializer.validated_data["challenge_token"],
                serializer.validated_data["code"],
                request,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)
        refresh_str = str(refresh)
        security_service.record_login(user, request, success=True, refresh_token=refresh_str)
        response = Response({
            "access": access,
            "refresh": refresh_str,
        })
        set_auth_cookies(response, access, refresh_str)
        return response


class TwoFactorLoginSendOtpView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    @extend_schema(tags=["Security"], summary="Send 2FA email OTP during login")
    def post(self, request):
        token = request.data.get("challenge_token")
        if not token:
            return Response({"detail": "challenge_token required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            security_service.send_login_2fa_otp(token)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"sent": True})


class DeviceListView(APIView):
    @extend_schema(tags=["Security"], summary="List active devices")
    def get(self, request):
        devices = security_service.list_devices(
            request.user, current_device_id=_current_device_id(request)
        )
        serializer = UserDeviceSerializer(
            devices,
            many=True,
            context={"current_device_id": _current_device_id(request)},
        )
        return Response({"devices": serializer.data})


class DeviceRenameView(APIView):
    @extend_schema(tags=["Security"], summary="Rename a device")
    def patch(self, request, device_id: int):
        serializer = DeviceRenameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = security_service.rename_device(
            request.user, device_id, serializer.validated_data["device_name"]
        )
        return Response(
            UserDeviceSerializer(device, context={"current_device_id": _current_device_id(request)}).data
        )


class DeviceTrustView(APIView):
    @extend_schema(tags=["Security"], summary="Trust a device")
    def post(self, request, device_id: int):
        device = security_service.trust_device(request.user, device_id)
        return Response(
            UserDeviceSerializer(device, context={"current_device_id": _current_device_id(request)}).data
        )


class DeviceUntrustView(APIView):
    @extend_schema(tags=["Security"], summary="Remove device trust")
    def post(self, request, device_id: int):
        device = security_service.untrust_device(request.user, device_id)
        return Response(
            UserDeviceSerializer(device, context={"current_device_id": _current_device_id(request)}).data
        )


class DeviceLogoutView(APIView):
    @extend_schema(tags=["Security"], summary="Logout a specific device session")
    def post(self, request, device_id: int):
        from .models import UserSession

        session = (
            UserSession.objects.filter(device_id=device_id, user=request.user, is_active=True)
            .order_by("-last_active")
            .first()
        )
        if not session:
            return Response({"detail": "No active session for this device."}, status=status.HTTP_404_NOT_FOUND)
        try:
            security_service.revoke_session(
                request.user, session.id, current_jti=_current_jti(request)
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"logged_out": True})


class LogoutAllDevicesView(APIView):
    @extend_schema(tags=["Security"], summary="Logout from all devices")
    def post(self, request):
        serializer = LogoutAllSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        count = security_service.revoke_all_sessions(
            request.user,
            keep_current=serializer.validated_data["keep_current"],
            current_jti=_current_jti(request),
        )
        return Response({"revoked": count, "message": f"Signed out of {count} device(s)."})


class LoginHistoryView(APIView):
    @extend_schema(tags=["Security"], summary="Login history")
    def get(self, request):
        search = request.query_params.get("search", "")
        success = request.query_params.get("success")
        page = int(request.query_params.get("page", 1))
        page_size = min(int(request.query_params.get("page_size", 20)), 50)
        success_only = None
        if success == "true":
            success_only = True
        elif success == "false":
            success_only = False

        entries, total = security_service.list_login_history(
            request.user,
            search=search,
            success_only=success_only,
            page=page,
            page_size=page_size,
        )
        return Response({
            "results": LoginHistorySerializer(entries, many=True).data,
            "total": total,
            "page": page,
            "page_size": page_size,
        })


class SecurityEventsView(APIView):
    @extend_schema(tags=["Security"], summary="Security alerts")
    def get(self, request):
        unread_only = request.query_params.get("unread") == "true"
        version = get_user_cache_version(request.user.id)
        cache_key = cache_keys.security_events(request.user.id, version, unread_only)

        def build():
            events = security_service.list_events(request.user, unread_only=unread_only)
            return {"events": SecurityEventSerializer(events, many=True).data}

        return Response(
            api_cache.get_or_set(
                cache_key,
                build,
                cache_ttl.SECURITY_EVENTS,
                label="security_events",
            )
        )


class SecurityEventReadView(APIView):
    @extend_schema(tags=["Security"], summary="Mark security alert as read")
    def post(self, request, event_id: int):
        event = security_service.mark_event_read(request.user, event_id)
        invalidate_user_caches(request.user.id, reason="security_event_read")
        return Response(SecurityEventSerializer(event).data)


class SecurityEventsReadAllView(APIView):
    @extend_schema(tags=["Security"], summary="Mark all security alerts as read")
    def post(self, request):
        count = security_service.mark_all_events_read(request.user)
        invalidate_user_caches(request.user.id, reason="security_events_read_all")
        return Response({"marked": count})


class BiometricEnableView(APIView):
    @extend_schema(tags=["Security"], summary="Enable biometric login")
    def post(self, request):
        serializer = BiometricEnableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token, device = security_service.enable_biometric(
                request.user,
                request,
                serializer.validated_data["password"],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            "enabled": True,
            "token": token,
            "device_id": device.device_id,
        })


class BiometricDisableView(APIView):
    @extend_schema(tags=["Security"], summary="Disable biometric login")
    def post(self, request):
        serializer = PasswordVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            security_service.disable_biometric(request.user, serializer.validated_data["password"])
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"disabled": True})


class BiometricStatusView(APIView):
    @extend_schema(tags=["Security"], summary="Biometric login status")
    def get(self, request):
        device_id = _current_device_id(request)
        data = security_service.biometric_status(request.user, device_id)
        return Response(BiometricStatusSerializer(data).data)


class BiometricLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    @extend_schema(tags=["Security"], summary="Login with biometric token")
    def post(self, request):
        serializer = BiometricLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = security_service.biometric_login(
            request,
            serializer.validated_data["token"],
            serializer.validated_data["device_id"],
        )
        if not user:
            return Response({"detail": "Invalid biometric credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)
        refresh_str = str(refresh)
        security_service.record_login(user, request, success=True, refresh_token=refresh_str)
        response = Response({"access": access, "refresh": refresh_str})
        set_auth_cookies(response, access, refresh_str)
        return response
