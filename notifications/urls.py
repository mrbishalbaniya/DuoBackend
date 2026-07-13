from django.urls import path

from notifications.views import (
    AdminBroadcastView,
    DeviceTokenRegisterView,
    DeviceTokenUnregisterAllView,
    DeviceTokenUnregisterView,
    InboxWebSocketTicketView,
    NotificationConfigView,
    NotificationPreferenceView,
)

urlpatterns = [
    path("config/", NotificationConfigView.as_view(), name="notifications-config"),
    path("devices/", DeviceTokenRegisterView.as_view(), name="notifications-device-register"),
    path(
        "devices/unregister/",
        DeviceTokenUnregisterView.as_view(),
        name="notifications-device-unregister",
    ),
    path(
        "devices/unregister-all/",
        DeviceTokenUnregisterAllView.as_view(),
        name="notifications-device-unregister-all",
    ),
    path("preferences/", NotificationPreferenceView.as_view(), name="notifications-preferences"),
    path("ws-ticket/", InboxWebSocketTicketView.as_view(), name="notifications-ws-ticket"),
    path("admin/broadcast/", AdminBroadcastView.as_view(), name="notifications-admin-broadcast"),
]
