from django.conf import settings
from rest_framework.permissions import BasePermission


class OtaPublishTokenPermission(BasePermission):
    """Authorize CI publish requests via OTA_PUBLISH_TOKEN header."""

    def has_permission(self, request, view) -> bool:
        expected = getattr(settings, "OTA_PUBLISH_TOKEN", "").strip()
        if not expected:
            return False
        provided = (request.headers.get("X-OTA-Token") or "").strip()
        return provided == expected
