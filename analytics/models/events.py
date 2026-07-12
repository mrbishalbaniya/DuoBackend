from django.conf import settings
from django.db import models

from analytics.constants import EVENT_CATEGORIES


class AnalyticsEvent(models.Model):
    """Append-only event store for behavioral and business analytics."""

    category = models.CharField(max_length=32, choices=EVENT_CATEGORIES, db_index=True)
    event_type = models.CharField(max_length=64, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analytics_events",
    )
    session_id = models.CharField(max_length=64, blank=True, default="")
    device_id = models.CharField(max_length=128, blank=True, default="")
    platform = models.CharField(max_length=16, blank=True, default="")
    country = models.CharField(max_length=64, blank=True, default="")
    city = models.CharField(max_length=128, blank=True, default="")
    properties = models.JSONField(default=dict, blank=True)
    value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    occurred_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["category", "event_type", "-occurred_at"]),
            models.Index(fields=["user", "-occurred_at"]),
            models.Index(fields=["platform", "-occurred_at"]),
        ]

    def __str__(self):
        return f"{self.category}.{self.event_type} @ {self.occurred_at:%Y-%m-%d %H:%M}"
