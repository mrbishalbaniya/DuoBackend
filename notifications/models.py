from django.conf import settings
from django.db import models


class DeviceToken(models.Model):
    PLATFORM_WEB = "web"
    PLATFORM_ANDROID = "android"
    PLATFORM_IOS = "ios"
    PLATFORM_CHOICES = [
        (PLATFORM_WEB, "Web"),
        (PLATFORM_ANDROID, "Android"),
        (PLATFORM_IOS, "iOS"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_tokens",
    )
    token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(
        max_length=16,
        choices=PLATFORM_CHOICES,
        default=PLATFORM_WEB,
    )
    user_agent = models.CharField(max_length=512, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.platform}:{self.token[:12]}…"
