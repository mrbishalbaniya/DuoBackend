from django.urls import path

from admin_portal.api import views

urlpatterns = [
    path("dashboard/", views.PortalDashboardAPIView.as_view(), name="portal-dashboard"),
    path("search/", views.PortalSearchAPIView.as_view(), name="portal-search"),
    path("notifications/", views.PortalNotificationsAPIView.as_view(), name="portal-notifications"),
    path("activity/", views.PortalActivityAPIView.as_view(), name="portal-activity"),
    path("commands/", views.PortalCommandPaletteAPIView.as_view(), name="portal-commands"),
]
