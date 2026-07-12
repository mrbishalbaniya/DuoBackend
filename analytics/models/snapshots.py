from django.db import models


class HourlyMetricSnapshot(models.Model):
    """Pre-aggregated hourly metrics for fast dashboard queries."""

    bucket_start = models.DateTimeField(db_index=True, unique=True)
    metrics = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-bucket_start"]

    def __str__(self):
        return f"Hourly {self.bucket_start:%Y-%m-%d %H:00}"


class DailyMetricSnapshot(models.Model):
    """Pre-aggregated daily metrics — materialized view equivalent."""

    date = models.DateField(db_index=True, unique=True)
    metrics = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Daily {self.date}"


class FunnelSnapshot(models.Model):
    """Daily funnel stage counts for drop-off analysis."""

    date = models.DateField(db_index=True)
    funnel_name = models.CharField(max_length=64, default="onboarding")
    stages = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("date", "funnel_name")]
        ordering = ["-date"]

    def __str__(self):
        return f"Funnel {self.funnel_name} · {self.date}"


class CohortSnapshot(models.Model):
    """Cached cohort retention matrix."""

    cohort_date = models.DateField(db_index=True)
    period_days = models.PositiveSmallIntegerField()
    cohort_size = models.PositiveIntegerField(default=0)
    retained_users = models.PositiveIntegerField(default=0)
    retention_rate = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("cohort_date", "period_days")]
        ordering = ["-cohort_date", "period_days"]

    def __str__(self):
        return f"Cohort {self.cohort_date} D{self.period_days}: {self.retention_rate}%"
