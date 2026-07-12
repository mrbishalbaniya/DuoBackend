from django.conf import settings
from django.db import models


class AnalyticsAuditLog(models.Model):
    ACTIONS = [
        ("view_dashboard", "View Dashboard"),
        ("export_report", "Export Report"),
        ("create_report", "Create Report"),
        ("update_report", "Update Report"),
        ("delete_report", "Delete Report"),
        ("schedule_report", "Schedule Report"),
        ("share_dashboard", "Share Dashboard"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="analytics_audit_logs",
    )
    action = models.CharField(max_length=32, choices=ACTIONS)
    resource_type = models.CharField(max_length=64, blank=True, default="")
    resource_id = models.CharField(max_length=64, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.action} by {self.user_id} @ {self.created_at:%Y-%m-%d %H:%M}"
