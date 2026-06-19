from rest_framework import generics, permissions, status, parsers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.db.models import Q
from django.utils import timezone
from .serializers import (
    RegisterSerializer,
    UserSerializer,
    ProfileSerializer,
    GoogleAuthSerializer,
    FirebasePhoneVerifySerializer,
    FirebaseAuthSerializer,
    EmailOtpSendSerializer,
    EmailOtpVerifySerializer,
)
from .google_auth import get_or_create_google_user, verify_google_id_token
from .phone_auth import get_or_create_phone_user, verify_firebase_phone_token
from .email_otp import send_email_otp, verify_email_otp
from .models import Profile
from .geo import profile_coordinates, haversine_km, CITY_COORDS
from matching.models import Swipe


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class GoogleAuthView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            idinfo = verify_google_id_token(serializer.validated_data["id_token"])
            user, _created = get_or_create_google_user(idinfo)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class FirebasePhoneVerifyView(APIView):
    """Verify Firebase phone OTP during registration."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = FirebasePhoneVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        expected_phone = (serializer.validated_data.get("phone") or "").strip() or None

        try:
            phone = verify_firebase_phone_token(
                serializer.validated_data["id_token"],
                expected_phone=expected_phone,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Invalid or expired Firebase token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"verified": True, "phone": phone}, status=status.HTTP_200_OK)


class EmailOtpSendView(APIView):
    """Send a 6-digit verification code to an email address."""

    permission_classes = [permissions.AllowAny]

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
        except Exception:
            return Response(
                {"detail": "Could not send verification email. Check Gmail SMTP settings."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({"sent": True, "email": email}, status=status.HTTP_200_OK)


class EmailOtpVerifyView(APIView):
    """Verify a 6-digit email OTP during registration."""

    permission_classes = [permissions.AllowAny]

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


class FirebaseAuthView(APIView):
    """Login or sign-up with a Firebase ID token (phone OTP)."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = FirebaseAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            phone = verify_firebase_phone_token(serializer.validated_data["id_token"])
            user, _created = get_or_create_phone_user(phone)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Invalid or expired Firebase token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class MyProfileView(APIView):
    def get(self, request):
        return Response(ProfileSerializer(request.user.profile).data)

    def put(self, request):
        serializer = ProfileSerializer(request.user.profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ProfilePhotoUploadView(APIView):
    """Upload a profile photo during registration or profile editing."""

    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request):
        image = request.data.get("image")
        if not image:
            return Response({"detail": "No image provided."}, status=status.HTTP_400_BAD_REQUEST)

        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"profile_{request.user.id}_{timestamp}_{image.name}"
        saved_path = default_storage.save(f"profile_photos/{filename}", image)
        image_url = request.build_absolute_uri(f"{settings.MEDIA_URL}{saved_path}")
        return Response({"image_url": image_url}, status=status.HTTP_201_CREATED)


class DiscoverView(APIView):
    """Get profiles to swipe on (excludes self and already-swiped profiles)."""

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


class ProfileDetailView(generics.RetrieveAPIView):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
