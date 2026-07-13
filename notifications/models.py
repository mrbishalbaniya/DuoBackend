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
    device_label = models.CharField(max_length=128, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["platform", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.platform}:{self.token[:12]}…"


class NotificationPreference(models.Model):
    """Per-user push notification preferences."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    push_enabled = models.BooleanField(default=True)
    chat_enabled = models.BooleanField(default=True)
    calls_enabled = models.BooleanField(default=True)
    match_enabled = models.BooleanField(default=True)
    likes_enabled = models.BooleanField(default=True)
    marketing_enabled = models.BooleanField(default=False)
    announcements_enabled = models.BooleanField(default=True)
    verification_enabled = models.BooleanField(default=True)
    payment_enabled = models.BooleanField(default=True)
    sound_enabled = models.BooleanField(default=True)
    vibration_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Notification preferences"

    def __str__(self) -> str:
        return f"prefs:{self.user_id}"


class PushDeliveryLog(models.Model):
    """Delivery audit trail for admin observability."""

    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = [
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
        (STATUS_SKIPPED, "Skipped"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_delivery_logs",
    )
    notification_type = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES)
    devices_targeted = models.PositiveIntegerField(default=0)
    devices_sent = models.PositiveIntegerField(default=0)
    skip_reason = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "notification_type", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.notification_type}:{self.user_id}:{self.status}"
