import secrets

from django.core.cache import cache
from django.core.signing import TimestampSigner
from django.shortcuts import redirect
from urllib.parse import urlencode
from rest_framework import generics, permissions, status, parsers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from duo_project.cloudinary_media.responses import upload_response_dict
from duo_project.cloudinary_upload import CloudinaryNotConfiguredError, upload_profile_photo_result
from photo_verification.constants import PhotoStatus
from photo_verification.services.pipeline import PhotoVerificationPipeline
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
from google.auth.exceptions import GoogleAuthError
from .auth_cookies import set_auth_cookies
from .throttling import AuthRateThrottle, UploadRateThrottle
from .serializers import (
    RegisterSerializer,
    UserSerializer,
    ProfileSerializer,
    GoogleAuthSerializer,
    EmailOtpSendSerializer,
    EmailOtpVerifySerializer,
    PasswordForgotSerializer,
    PasswordResetSerializer,
    PasswordChangeSerializer,
)
from .google_auth import (
    exchange_google_auth_code,
    get_or_create_google_user,
    verify_google_id_token,
)
from .email_otp import send_email_otp, verify_email_otp
from .password_reset import (
    clear_password_reset_otp,
    send_password_reset_otp,
    verify_password_reset_otp,
)
from .models import Profile
from .serializer_context import profile_list_serializer_context
from matching.recommendation import discover_profiles
from matching.profile_visits import record_profile_visit
from duo_project.cache import api_cache, get_user_cache_version
from duo_project.cache import keys as cache_keys
from duo_project.cache import ttl as cache_ttl
from duo_project.cache.invalidation import invalidate_profile_caches, invalidate_user_caches
from duo_project.cache.lookups import get_static_lookups

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        tags=["Authentication"],
        summary="Register a new account",
        responses={201: UserSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        from accounts.email_otp import clear_email_verified

        clear_email_verified(user.email)
        refresh = RefreshToken.for_user(user)
        response = Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)
        set_auth_cookies(response, str(refresh.access_token), str(refresh))
        return response


class MeView(APIView):
    @extend_schema(tags=["Authentication"], summary="Get current authenticated user")
    def get(self, request):
        def build():
            return UserSerializer(request.user).data

        data = api_cache.get_or_set(
            cache_keys.user(request.user.id),
            build,
            cache_ttl.USER,
            label="user_me",
        )
        return Response(data)


class GoogleAuthView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        tags=["Authentication"],
        summary="Sign in with Google ID token",
        request=GoogleAuthSerializer,
        responses={200: UserSerializer},
        auth=[],
    )
    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            validated = serializer.validated_data
            if validated.get("code"):
                id_token = exchange_google_auth_code(
                    validated["code"],
                    validated["redirect_uri"],
                )
            else:
                id_token = validated["id_token"]

            idinfo = verify_google_id_token(id_token)
            user, _created = get_or_create_google_user(idinfo)
        except (ValueError, GoogleAuthError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        refresh = RefreshToken.for_user(user)
        response = Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )
        set_auth_cookies(response, str(refresh.access_token), str(refresh))
        return response


class GoogleOAuthCallbackView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    def get(self, request):
        error = request.GET.get("error")
        code = request.GET.get("code")
        state = request.GET.get("state", "")
        login_error_url = f"{settings.FRONTEND_URL}/login?error=google_auth"

        if state == "duo_mobile":
            if error or not code:
                params = urlencode({"error": error or "access_denied"})
            else:
                params = urlencode({"code": code})
            return redirect(f"com.duo.duo_mobile://oauth2redirect?{params}")

        if error or not code:
            return redirect(login_error_url)

        try:
            from duo_project.runtime_config import get_integration_settings

            cfg = get_integration_settings()
            id_token = exchange_google_auth_code(code, cfg.google_redirect_uri)
            idinfo = verify_google_id_token(id_token)
            user, _created = get_or_create_google_user(idinfo)
        except (ValueError, GoogleAuthError):
            return redirect(login_error_url)
        except Exception:
            return redirect(login_error_url)

        refresh = RefreshToken.for_user(user)
        try:
            onboarded = user.profile.is_onboarded
        except Profile.DoesNotExist:
            onboarded = False

        import secrets

        handoff_id = secrets.token_urlsafe(32)
        cache.set(
            f"auth_handoff:{handoff_id}",
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "onboarded": onboarded,
            },
            timeout=120,
        )
        params = urlencode({"handoff": handoff_id})
        return redirect(f"{settings.FRONTEND_URL}/login/google/complete?{params}")


class EmailOtpSendView(APIView):
    """Send a 6-digit verification code to an email address."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        tags=["Authentication"],
        summary="Send email OTP for registration",
        request=EmailOtpSendSerializer,
        auth=[],
    )
    def post(self, request):
        serializer = EmailOtpSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            # Prevent email enumeration — same response shape as success.
            return Response({"sent": True, "email": email}, status=status.HTTP_200_OK)

        try:
            send_email_otp(email)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except TimeoutError:
            return Response(
                {"detail": "Email server timed out. Check Integration settings in the admin."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception:
            return Response(
                {"detail": "Could not send verification email. Check email settings in the admin."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({"sent": True, "email": email}, status=status.HTTP_200_OK)


class EmailOtpVerifyView(APIView):
    """Verify a 6-digit email OTP during registration."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        tags=["Authentication"],
        summary="Verify email OTP code",
        request=EmailOtpVerifySerializer,
        auth=[],
    )
    def post(self, request):
        serializer = EmailOtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        otp = serializer.validated_data["otp"].strip()

        if verify_email_otp(email, otp):
            return Response({"verified": True, "email": email}, status=status.HTTP_200_OK)

        return Response(
            {"detail": "Invalid or expired verification code."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class PasswordForgotView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        tags=["Authentication"],
        summary="Request a password reset code",
        request=PasswordForgotSerializer,
        auth=[],
    )
    def post(self, request):
        serializer = PasswordForgotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()

        user = User.objects.filter(email__iexact=email).first()
        if user and user.has_usable_password():
            try:
                send_password_reset_otp(email)
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except RuntimeError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except Exception:
                return Response(
                    {"detail": "Could not send password reset email. Check email settings in the admin."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(
            {
                "sent": True,
                "message": "If an account exists for this email, a reset code has been sent.",
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    @extend_schema(
        tags=["Authentication"],
        summary="Reset password with email OTP",
        request=PasswordResetSerializer,
        auth=[],
    )
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].strip().lower()
        otp = serializer.validated_data["otp"].strip()
        password = serializer.validated_data["password"]

        user = User.objects.filter(email__iexact=email).first()
        if not user or not user.has_usable_password():
            return Response(
                {"detail": "Invalid or expired reset code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not verify_password_reset_otp(email, otp):
            return Response(
                {"detail": "Invalid or expired reset code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)
        user.save(update_fields=["password"])
        clear_password_reset_otp(email)

        return Response(
            {"reset": True, "message": "Password updated successfully."},
            status=status.HTTP_200_OK,
        )


class PasswordChangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Authentication"],
        summary="Change password for the authenticated user",
        request=PasswordChangeSerializer,
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.has_usable_password():
            return Response(
                {
                    "detail": (
                        "This account uses Google sign-in. "
                        "Use Forgot password on the login page to set a password."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        current_password = serializer.validated_data["current_password"]
        new_password = serializer.validated_data["new_password"]

        if not user.check_password(current_password):
            return Response(
                {"detail": "Current password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])

        try:
            from security.services import security_service

            security_service.on_password_changed(user, request)
        except Exception:
            pass

        return Response(
            {"changed": True, "message": "Password updated successfully."},
            status=status.HTTP_200_OK,
        )


class MyProfileView(APIView):
    @extend_schema(tags=["Profiles"], summary="Get my profile")
    def get(self, request):
        def build():
            context = profile_list_serializer_context(request, [request.user.profile])
            return ProfileSerializer(request.user.profile, context=context).data

        data = api_cache.get_or_set(
            cache_keys.profile(request.user.profile.id),
            build,
            cache_ttl.PROFILE,
            label="profile_me",
        )
        return Response(data)

    @extend_schema(
        tags=["Profiles"],
        summary="Update my profile",
        request=ProfileSerializer,
        responses={200: ProfileSerializer},
    )
    def put(self, request):
        serializer = ProfileSerializer(
            request.user.profile,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        invalidate_profile_caches(request.user.profile.id, request.user.id, reason="profile_update")
        return Response(serializer.data)


class ProfilePhotoUploadView(APIView):
    """Upload a profile photo during registration or profile editing."""

    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    throttle_classes = [UploadRateThrottle]

    @extend_schema(
        tags=["Profiles"],
        summary="Upload a profile photo",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"image": {"type": "string", "format": "binary"}},
                "required": ["image"],
            }
        },
        responses={201: OpenApiResponse(description="Returns uploaded image URL.")},
    )
    def post(self, request):
        image = request.data.get("image")
        if not image:
            return Response({"detail": "No image provided."}, status=status.HTTP_400_BAD_REQUEST)

        pipeline = PhotoVerificationPipeline()
        try:
            result = pipeline.analyze_file(image, user_id=request.user.id)
        except Exception as exc:
            detail = f"Image analysis failed: {exc}" if settings.DEBUG else "Image analysis failed."
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

        if not result.face_detected:
            return Response(
                {"detail": "No human face detected. Please upload a clear photo showing your face."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        strict_reject = getattr(settings, "PHOTO_VERIFICATION_STRICT_REJECT", True)
        if result.status == PhotoStatus.REJECTED and strict_reject:
            return Response(
                {"detail": "; ".join(result.rejection_reasons) or "Photo rejected."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        try:
            image.seek(0)
            upload_result = upload_profile_photo_result(
                image,
                user_id=request.user.id,
                replace_url=getattr(request.user.profile, "photo_url", None) or None,
            )
        except CloudinaryNotConfiguredError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        invalidate_profile_caches(request.user.profile.id, request.user.id, reason="photo_upload")
        return Response(upload_response_dict(upload_result), status=status.HTTP_201_CREATED)


class DiscoverView(APIView):
    """Get profiles to swipe on (excludes self and already-swiped profiles)."""

    @extend_schema(
        tags=["Discovery"],
        summary="Discover profiles to swipe",
        responses={200: ProfileSerializer(many=True)},
    )
    def get(self, request):
        version = get_user_cache_version(request.user.id)
        cache_key = cache_keys.discover(request.user.id, version)

        def build():
            return self._build_discover_payload(request)

        payload = api_cache.get_or_set(
            cache_key,
            build,
            cache_ttl.DISCOVER,
            label="discover",
        )
        if isinstance(payload, list):
            response = Response(payload)
            return response

        response = Response(payload["profiles"])
        if payload.get("expanded_search"):
            response["X-Duo-Discover-Expanded"] = "1"
        return response

    @staticmethod
    def _build_discover_payload(request):
        result = discover_profiles(request.user)
        context = profile_list_serializer_context(request, result.profiles)
        return {
            "profiles": ProfileSerializer(result.profiles, many=True, context=context).data,
            "expanded_search": result.expanded_search or result.recycled_skips,
            "recycled_skips": result.recycled_skips,
        }


class ProfileLookupsView(APIView):
    """Cached static profile/discovery lookup tables."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Profiles"], summary="Get static profile lookup tables")
    def get(self, request):
        return Response(get_static_lookups())


@extend_schema_view(
    get=extend_schema(tags=["Profiles"], summary="Get profile by ID"),
)
class ProfileDetailView(generics.RetrieveAPIView):
    queryset = Profile.objects.select_related("user")
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def retrieve(self, request, *args, **kwargs):
        profile = self.get_object()
        record_profile_visit(request.user, profile.user)

        cache_key = cache_keys.profile_public(
            profile.id,
            request.user.id,
            get_user_cache_version(profile.user_id),
        )

        def build():
            serializer = self.get_serializer(
                profile,
                context=profile_list_serializer_context(request, [profile]),
            )
            return serializer.data

        data = api_cache.get_or_set(
            cache_key,
            build,
            cache_ttl.PROFILE_PUBLIC,
            label="profile_detail",
        )
        return Response(data)


class ProfileVisitRecordView(APIView):
    """Record that the current user viewed another member's profile."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Profiles"],
        summary="Record a profile view",
        responses={204: OpenApiResponse(description="Recorded")},
    )
    def post(self, request, pk):
        try:
            profile = Profile.objects.select_related("user").get(pk=pk)
        except Profile.DoesNotExist:
            return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

        record_profile_visit(request.user, profile.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
