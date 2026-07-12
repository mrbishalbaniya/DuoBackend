from django.urls import path

from analytics.api import views

urlpatterns = [
    path("dashboard/executive/", views.ExecutiveDashboardView.as_view(), name="analytics-executive"),
    path("dashboard/realtime/", views.RealtimeDashboardView.as_view(), name="analytics-realtime"),
    path("revenue/", views.RevenueAnalyticsView.as_view(), name="analytics-revenue"),
    path("revenue/timeseries/", views.RevenueTimeseriesView.as_view(), name="analytics-revenue-timeseries"),
    path("users/", views.UserAnalyticsView.as_view(), name="analytics-users"),
    path("matching/", views.MatchingAnalyticsView.as_view(), name="analytics-matching"),
    path("chat/", views.ChatAnalyticsView.as_view(), name="analytics-chat"),
    path("maps/", views.MapAnalyticsView.as_view(), name="analytics-maps"),
    path("funnel/", views.FunnelAnalyticsView.as_view(), name="analytics-funnel"),
    path("retention/", views.RetentionAnalyticsView.as_view(), name="analytics-retention"),
    path("behavior/", views.BehaviorAnalyticsView.as_view(), name="analytics-behavior"),
    path("forecast/", views.ForecastAnalyticsView.as_view(), name="analytics-forecast"),
    path("security/", views.SecurityAnalyticsView.as_view(), name="analytics-security"),
    path("fraud/", views.FraudAnalyticsView.as_view(), name="analytics-fraud"),
    path("system/", views.SystemAnalyticsView.as_view(), name="analytics-system"),
    path("events/", views.AnalyticsEventListView.as_view(), name="analytics-events"),
    path("exports/", views.ExportView.as_view(), name="analytics-exports"),
    path("reports/<str:report_type>/", views.ReportPreviewView.as_view(), name="analytics-report-preview"),
    path("dashboards/", views.SavedDashboardListCreateView.as_view(), name="analytics-dashboards"),
    path("saved-reports/", views.SavedReportListCreateView.as_view(), name="analytics-saved-reports"),
    path("snapshots/daily/", views.DailySnapshotListView.as_view(), name="analytics-daily-snapshots"),
]
