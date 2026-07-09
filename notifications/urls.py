from django.urls import path

from notifications.views import (
    DeviceTokenRegisterView,
    DeviceTokenUnregisterView,
    NotificationConfigView,
)

urlpatterns = [
    path("config/", NotificationConfigView.as_view(), name="notifications-config"),
    path("devices/", DeviceTokenRegisterView.as_view(), name="notifications-device-register"),
    path(
        "devices/unregister/",
        DeviceTokenUnregisterView.as_view(),
        name="notifications-device-unregister",
    ),
]
