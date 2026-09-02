from django.conf import settings
from django.db import models


class SupportRequestCategory(models.TextChoices):
    CONTACT = "contact", "Contact support"
    BUG = "bug", "Report a bug"


class SupportRequestStatus(models.TextChoices):
    OPEN = "open", "Open"
    IN_PROGRESS = "in_progress", "In progress"
    RESOLVED = "resolved", "Resolved"


class SupportRequest(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_requests",
    )
    category = models.CharField(max_length=16, choices=SupportRequestCategory.choices)
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    contact_email = models.EmailField(blank=True)
    device_info = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=16, choices=SupportRequestStatus.choices, default=SupportRequestStatus.OPEN
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at"]), models.Index(fields=["status"])]

    def __str__(self):
        return f"[{self.get_category_display()}] {self.subject or self.message[:40]}"
