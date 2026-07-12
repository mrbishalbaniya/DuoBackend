from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from duo_project.runtime_config import get_integration_settings
from notifications.models import DeviceToken
from notifications.serializers import DeviceTokenSerializer


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

    # Android / iOS — VAPID is web-only; mobile only needs Firebase core + platform app ID.
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
        user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:512]

        DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                "user": request.user,
                "platform": platform,
                "user_agent": user_agent,
                "is_active": True,
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
