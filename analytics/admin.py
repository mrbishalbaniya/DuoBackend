from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html

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
from analytics.views.dashboard import analytics_dashboard_view


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "category", "user", "platform", "occurred_at")
    list_filter = ("category", "event_type", "platform")
    search_fields = ("event_type", "user__username")
    readonly_fields = ("created_at",)
    date_hierarchy = "occurred_at"


@admin.register(DailyMetricSnapshot)
class DailyMetricSnapshotAdmin(admin.ModelAdmin):
    list_display = ("date", "updated_at")
    date_hierarchy = "date"


@admin.register(HourlyMetricSnapshot)
class HourlyMetricSnapshotAdmin(admin.ModelAdmin):
    list_display = ("bucket_start", "updated_at")
    date_hierarchy = "bucket_start"


@admin.register(FunnelSnapshot)
class FunnelSnapshotAdmin(admin.ModelAdmin):
    list_display = ("date", "funnel_name", "created_at")
    list_filter = ("funnel_name",)


@admin.register(CohortSnapshot)
class CohortSnapshotAdmin(admin.ModelAdmin):
    list_display = ("cohort_date", "period_days", "cohort_size", "retention_rate")
    list_filter = ("period_days",)


@admin.register(SavedDashboard)
class SavedDashboardAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "is_shared", "is_favorite", "updated_at")
    search_fields = ("name", "owner__username")


@admin.register(SavedReport)
class SavedReportAdmin(admin.ModelAdmin):
    list_display = ("name", "report_type", "owner", "is_favorite", "updated_at")
    list_filter = ("report_type",)


@admin.register(ScheduledReport)
class ScheduledReportAdmin(admin.ModelAdmin):
    list_display = ("report", "frequency", "export_format", "is_active", "next_run_at")
    list_filter = ("frequency", "is_active")


@admin.register(AnalyticsAuditLog)
class AnalyticsAuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "user", "resource_type", "ip_address", "created_at")
    list_filter = ("action",)
    readonly_fields = ("created_at",)


class AnalyticsAdminSite(admin.AdminSite):
    site_header = "Duo Analytics"
    site_title = "Duo Analytics Platform"
    index_title = "Business Intelligence"


def register_analytics_admin_hooks():
    """Inject analytics dashboard link into default admin."""
    original_get_urls = admin.site.get_urls

    def get_urls():
        custom = [
            path(
                "analytics/dashboard/",
                admin.site.admin_view(analytics_dashboard_view),
                name="analytics_dashboard",
            ),
        ]
        return custom + original_get_urls()

    admin.site.get_urls = get_urls


register_analytics_admin_hooks()
