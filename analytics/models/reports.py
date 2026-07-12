from django.conf import settings
from django.db import models


class SavedDashboard(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="analytics_dashboards",
    )
    name = models.CharField(max_length=128)
    slug = models.SlugField(max_length=128)
    description = models.TextField(blank=True, default="")
    layout = models.JSONField(default=dict, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    is_shared = models.BooleanField(default=False)
    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("owner", "slug")]
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


class SavedReport(models.Model):
    REPORT_TYPES = [
        ("executive", "Executive Summary"),
        ("revenue", "Revenue"),
        ("users", "Users"),
        ("matching", "Matching"),
        ("chat", "Chat"),
        ("retention", "Retention"),
        ("funnel", "Funnel"),
        ("security", "Security"),
        ("custom", "Custom"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="analytics_reports",
    )
    name = models.CharField(max_length=128)
    report_type = models.CharField(max_length=32, choices=REPORT_TYPES)
    filters = models.JSONField(default=dict, blank=True)
    config = models.JSONField(default=dict, blank=True)
    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.name} ({self.report_type})"


class ScheduledReport(models.Model):
    FREQUENCIES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("yearly", "Yearly"),
    ]
    FORMATS = [
        ("pdf", "PDF"),
        ("xlsx", "Excel"),
        ("csv", "CSV"),
        ("json", "JSON"),
    ]

    report = models.ForeignKey(
        SavedReport,
        on_delete=models.CASCADE,
        related_name="schedules",
    )
    frequency = models.CharField(max_length=16, choices=FREQUENCIES)
    export_format = models.CharField(max_length=8, choices=FORMATS, default="pdf")
    recipients = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.report.name} · {self.frequency}"
