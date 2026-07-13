from django.utils import timezone
from django.core.signing import TimestampSigner
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from duo_project.runtime_config import get_integration_settings
from notifications.models import DeviceToken, NotificationPreference
from notifications.serializers import (
    AdminBroadcastSerializer,
    DeviceTokenSerializer,
    NotificationPreferenceSerializer,
)
from notifications.services.notification_service import send_push_to_users
from notifications.services.preferences import get_preferences, preference_payload


def _resolve_app_id(cfg, platform: str) -> str:
    if platform == "android":
        return (cfg.firebase_android_app_id or cfg.firebase_app_id or "").strip()
    if platform == "ios":
        return (cfg.firebase_ios_app_id or cfg.firebase_app_id or "").strip()
    return (cfg.firebase_app_id or "").strip()


def _public_fcm_config(request=None):
    cfg = get_integration_settings()
    if not cfg.fcm_enabled:
        return {"enabled": False}

    platform = "web"
    if request is not None:
        platform = (request.query_params.get("platform") or "web").strip().lower()

    firebase = {
        "apiKey": cfg.firebase_api_key,
        "authDomain": cfg.firebase_auth_domain,
        "projectId": cfg.firebase_project_id,
        "messagingSenderId": cfg.firebase_messaging_sender_id,
        "appId": _resolve_app_id(cfg, platform),
    }

    core_ready = all(
        [
            firebase["apiKey"],
            firebase["projectId"],
            firebase["messagingSenderId"],
            firebase["appId"],
        ]
    )
    if not core_ready:
        return {"enabled": False}

    if platform == "web":
        if not cfg.fcm_vapid_key:
            return {"enabled": False}
        return {
            "enabled": True,
            "firebase": firebase,
            "vapidKey": cfg.fcm_vapid_key,
        }

    return {
        "enabled": True,
        "firebase": firebase,
    }


@extend_schema(tags=["Notifications"])
class NotificationConfigView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(_public_fcm_config(request))


@extend_schema(tags=["Notifications"])
class DeviceTokenRegisterView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"].strip()
        platform = serializer.validated_data["platform"]
        device_label = (serializer.validated_data.get("device_label") or "")[:128]
        user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:512]

        # Deactivate duplicate tokens for this user on same platform (keep latest).
        DeviceToken.objects.filter(
            user=request.user,
            platform=platform,
            is_active=True,
        ).exclude(token=token).update(is_active=False)

        DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                "user": request.user,
                "platform": platform,
                "device_label": device_label,
                "user_agent": user_agent,
                "is_active": True,
                "last_used_at": timezone.now(),
            },
        )
        return Response({"detail": "Device token registered."}, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Notifications"])
class DeviceTokenUnregisterView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = (request.data.get("token") or "").strip()
        if not token:
            return Response({"detail": "token is required."}, status=status.HTTP_400_BAD_REQUEST)

        DeviceToken.objects.filter(user=request.user, token=token).update(is_active=False)
        return Response({"detail": "Device token removed."})


@extend_schema(tags=["Notifications"])
class DeviceTokenUnregisterAllView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        count = DeviceToken.objects.filter(user=request.user, is_active=True).update(
            is_active=False
        )
        return Response({"detail": "All device tokens removed.", "count": count})


@extend_schema(tags=["Notifications"])
class NotificationPreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        prefs = get_preferences(request.user)
        return Response(preference_payload(prefs))

    def patch(self, request):
        prefs = get_preferences(request.user)
        serializer = NotificationPreferenceSerializer(
            prefs,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(preference_payload(prefs))


@extend_schema(tags=["Notifications"])
class AdminBroadcastView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = AdminBroadcastSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user_ids = data.get("user_ids") or []
        if not user_ids:
            user_ids = list(
                DeviceToken.objects.filter(is_active=True)
                .values_list("user_id", flat=True)
                .distinct()
            )

        from django.conf import settings

        frontend = getattr(settings, "FRONTEND_URL", "").rstrip("/")
        url = data.get("url") or "/"
        link = url if url.startswith("http") else f"{frontend}{url}"

        sent = send_push_to_users(
            user_ids,
            notification_type=data["notification_type"],
            title=data["title"],
            body=data["body"],
            data={"url": url, "type": data["notification_type"]},
            link=link,
            respect_preferences=True,
        )

        return Response(
            {
                "detail": "Broadcast queued.",
                "users_targeted": len(user_ids),
                "devices_sent": sent,
            },
            status=status.HTTP_202_ACCEPTED,
        )


@extend_schema(tags=["Notifications"])
class InboxWebSocketTicketView(APIView):
    """Issue a short-lived signed ticket for inbox WebSocket authentication."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get inbox WebSocket connection ticket",
        responses={200: OpenApiResponse(description='{"ticket": "..."}')},
    )
    def post(self, request):
        signer = TimestampSigner(salt="duo-inbox-ws-ticket")
        ticket = signer.sign(str(request.user.id))
        return Response({"ticket": ticket})
