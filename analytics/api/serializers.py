from rest_framework import serializers

from analytics.models import (
    AnalyticsAuditLog,
    AnalyticsEvent,
    CohortSnapshot,
    DailyMetricSnapshot,
    FunnelSnapshot,
    HourlyMetricSnapshot,
    SavedDashboard,
    SavedReport,
    ScheduledReport,
)


class AnalyticsEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyticsEvent
        fields = [
            "id", "category", "event_type", "user", "platform",
            "country", "city", "properties", "value", "occurred_at",
        ]
        read_only_fields = fields


class SavedDashboardSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedDashboard
        fields = [
            "id", "name", "slug", "description", "layout", "filters",
            "is_shared", "is_favorite", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SavedReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedReport
        fields = [
            "id", "name", "report_type", "filters", "config",
            "is_favorite", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ScheduledReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduledReport
        fields = [
            "id", "report", "frequency", "export_format", "recipients",
            "is_active", "last_run_at", "next_run_at", "created_at",
        ]
        read_only_fields = ["id", "last_run_at", "next_run_at", "created_at"]


class DailyMetricSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyMetricSnapshot
        fields = ["id", "date", "metrics", "updated_at"]


class AnalyticsAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyticsAuditLog
        fields = ["id", "user", "action", "resource_type", "resource_id", "metadata", "created_at"]
        read_only_fields = fields
