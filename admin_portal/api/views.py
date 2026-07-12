from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import CookieJWTAuthentication
from admin_portal.services.activity import get_notifications, get_recent_activity
from admin_portal.services.dashboard import get_portal_dashboard
from admin_portal.services.search import global_search


class PortalDashboardAPIView(APIView):
    authentication_classes = [CookieJWTAuthentication, SessionAuthentication]
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(get_portal_dashboard(request.user))


class PortalSearchAPIView(APIView):
    authentication_classes = [CookieJWTAuthentication, SessionAuthentication]
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(global_search(request.query_params.get("q", "")))


class PortalNotificationsAPIView(APIView):
    authentication_classes = [CookieJWTAuthentication, SessionAuthentication]
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response({"notifications": get_notifications()})


class PortalActivityAPIView(APIView):
    authentication_classes = [CookieJWTAuthentication, SessionAuthentication]
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response({"activities": get_recent_activity()})


class PortalCommandPaletteAPIView(APIView):
    authentication_classes = [CookieJWTAuthentication, SessionAuthentication]
    permission_classes = [IsAdminUser]

    def get(self, request):
        from admin_portal.menu import PORTAL_MENU_GROUPS, QUICK_ACTIONS
        from django.urls import reverse

        commands = [
            {"label": "Dashboard", "url": reverse("admin:index"), "icon": "fas fa-house", "type": "navigate"},
            {"label": "Analytics", "url": "/admin/analytics/dashboard/", "icon": "fas fa-chart-pie", "type": "navigate"},
        ]
        for action in QUICK_ACTIONS:
            commands.append({**action, "type": "action"})
        for group in PORTAL_MENU_GROUPS:
            for item in group.get("items", []):
                if "url" in item:
                    commands.append({"label": item["label"], "url": item["url"], "icon": item.get("icon", ""), "type": "navigate"})
        return Response({"commands": commands})
