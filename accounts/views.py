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
from duo_project.cloudinary_upload import CloudinaryNotConfiguredError, upload_profile_photo
from photo_verification.constants import PhotoStatus
from photo_verification.services.pipeline import PhotoVerificationPipeline
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from google.auth.exceptions import GoogleAuthError
from .auth_cookies import set_auth_cookies
from .throttling import AuthRateThrottle
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
from .geo import profile_coordinates, haversine_km, CITY_COORDS
from matching.models import Swipe
from matching.profile_visits import record_profile_visit

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
        return Response(UserSerializer(request.user).data)


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
            return Response(
                {"detail": "An account with this email already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
        return Response(ProfileSerializer(request.user.profile).data)

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
        return Response(serializer.data)


class ProfilePhotoUploadView(APIView):
    """Upload a profile photo during registration or profile editing."""

    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

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
            return Response({"detail": f"Image analysis failed: {exc}"}, status=status.HTTP_400_BAD_REQUEST)

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
            image_url = upload_profile_photo(image, user_id=request.user.id)
        except CloudinaryNotConfiguredError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"image_url": image_url}, status=status.HTTP_201_CREATED)


class DiscoverView(APIView):
    """Get profiles to swipe on (excludes self and already-swiped profiles)."""

    @extend_schema(
        tags=["Discovery"],
        summary="Discover profiles to swipe",
        responses={200: ProfileSerializer(many=True)},
    )
    def get(self, request):
        user_profile = request.user.profile
        swiped_ids = Swipe.objects.filter(from_user=request.user).values_list(
            "to_user_id", flat=True
        )
        profiles = (
            Profile.objects.exclude(user=request.user)
            .exclude(user_id__in=swiped_ids)
            .filter(is_onboarded=True)
        )

        profiles = profiles.filter(
            age__gte=user_profile.pref_age_min,
            age__lte=user_profile.pref_age_max,
        )

        if user_profile.pref_gender == "women":
            profiles = profiles.filter(gender="F")
        elif user_profile.pref_gender == "men":
            profiles = profiles.filter(gender="M")

        if user_profile.pref_verified_only:
            profiles = profiles.filter(is_verified=True)

        if (
            user_profile.pref_relationship_goal
            and user_profile.pref_relationship_goal != "everyone"
        ):
            profiles = profiles.filter(
                Q(relationship_goal=user_profile.pref_relationship_goal)
                | Q(relationship_goal="")
            )

        location_pref = (user_profile.pref_location or "").strip()
        if location_pref:
            pref_lower = location_pref.lower()
            matched_cities = [city for city in CITY_COORDS if city in pref_lower]
            if matched_cities:
                city_query = Q()
                for city in matched_cities:
                    city_query |= Q(location__icontains=city)
                profiles = profiles.filter(city_query)
            else:
                city_part = location_pref.split(",")[0].strip()
                if city_part:
                    profiles = profiles.filter(location__icontains=city_part)

        candidates = list(profiles.order_by("?")[:40])
        user_coords = profile_coordinates(
            user_profile.location, user_profile.user_id
        )
        max_km = max(1, user_profile.pref_max_distance_km or 50)

        filtered = []
        for profile in candidates:
            coords = profile_coordinates(profile.location, profile.user_id)
            if haversine_km(user_coords, coords) <= max_km:
                filtered.append(profile)
            if len(filtered) >= 10:
                break

        return Response(ProfileSerializer(filtered, many=True).data)


@extend_schema_view(
    get=extend_schema(tags=["Profiles"], summary="Get profile by ID"),
)
class ProfileDetailView(generics.RetrieveAPIView):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def retrieve(self, request, *args, **kwargs):
        profile = self.get_object()
        record_profile_visit(request.user, profile.user)
        return super().retrieve(request, *args, **kwargs)


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
