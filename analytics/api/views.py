"""Analytics REST API views."""

from rest_framework import generics, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import CookieJWTAuthentication

from analytics.api.serializers import (
    AnalyticsAuditLogSerializer,
    AnalyticsEventSerializer,
    DailyMetricSnapshotSerializer,
    SavedDashboardSerializer,
    SavedReportSerializer,
    ScheduledReportSerializer,
)
from analytics.models import (
    AnalyticsAuditLog,
    AnalyticsEvent,
    DailyMetricSnapshot,
    SavedDashboard,
    SavedReport,
    ScheduledReport,
)
from analytics.permissions import AnalyticsModulePermission, IsAnalyticsUser, user_can_access_module
from analytics.services.behavior.analytics import get_behavior_analytics
from analytics.services.chat.analytics import get_chat_analytics
from analytics.services.dashboard.realtime import get_realtime_metrics
from analytics.services.exports.exporter import (
    build_report_data,
    export_csv,
    export_json,
    export_pdf,
    export_xlsx,
)
from analytics.services.forecast.analytics import get_forecast_analytics
from analytics.services.funnel.analytics import get_funnel_analytics
from analytics.services.kpi.executive import get_executive_dashboard, get_revenue_timeseries
from analytics.services.maps.analytics import get_map_analytics
from analytics.services.matching.analytics import get_matching_analytics
from analytics.services.retention.analytics import get_retention_analytics
from analytics.services.revenue.analytics import get_revenue_analytics
from analytics.services.security.analytics import get_fraud_signals, get_security_analytics
from analytics.services.system.analytics import get_system_analytics
from analytics.services.base import DateRange
from analytics.services.users.analytics import get_user_analytics


def _log_access(request, action: str, resource_type: str = "", resource_id: str = ""):
    AnalyticsAuditLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=request.META.get("REMOTE_ADDR"),
    )


class BaseAnalyticsView(APIView):
    authentication_classes = [CookieJWTAuthentication, SessionAuthentication]
    permission_classes = [IsAnalyticsUser, AnalyticsModulePermission]
    analytics_module = "dashboard"

    def get_filters(self, request):
        return dict(request.query_params.items())


class ExecutiveDashboardView(BaseAnalyticsView):
    analytics_module = "dashboard"

    def get(self, request):
        data = get_executive_dashboard(self.get_filters(request))
        _log_access(request, "view_dashboard", "executive")
        return Response(data)


class RealtimeDashboardView(BaseAnalyticsView):
    analytics_module = "dashboard"

    def get(self, request):
        return Response(get_realtime_metrics())


class RevenueAnalyticsView(BaseAnalyticsView):
    analytics_module = "revenue"

    def get(self, request):
        filters = self.get_filters(request)
        return Response(get_revenue_analytics(filters))


class RevenueTimeseriesView(BaseAnalyticsView):
    analytics_module = "revenue"

    def get(self, request):
        date_range = DateRange.from_request(self.get_filters(request))
        return Response({"timeseries": get_revenue_timeseries(date_range)})


class UserAnalyticsView(BaseAnalyticsView):
    analytics_module = "users"

    def get(self, request):
        return Response(get_user_analytics(self.get_filters(request)))


class MatchingAnalyticsView(BaseAnalyticsView):
    analytics_module = "matching"

    def get(self, request):
        return Response(get_matching_analytics(self.get_filters(request)))


class ChatAnalyticsView(BaseAnalyticsView):
    analytics_module = "chat"

    def get(self, request):
        return Response(get_chat_analytics(self.get_filters(request)))


class MapAnalyticsView(BaseAnalyticsView):
    analytics_module = "maps"

    def get(self, request):
        return Response(get_map_analytics(self.get_filters(request)))


class FunnelAnalyticsView(BaseAnalyticsView):
    analytics_module = "funnel"

    def get(self, request):
        return Response(get_funnel_analytics(self.get_filters(request)))


class RetentionAnalyticsView(BaseAnalyticsView):
    analytics_module = "retention"

    def get(self, request):
        return Response(get_retention_analytics(self.get_filters(request)))


class BehaviorAnalyticsView(BaseAnalyticsView):
    analytics_module = "behavior"

    def get(self, request):
        return Response(get_behavior_analytics(self.get_filters(request)))


class ForecastAnalyticsView(BaseAnalyticsView):
    analytics_module = "forecast"

    def get(self, request):
        return Response(get_forecast_analytics(self.get_filters(request)))


class SecurityAnalyticsView(BaseAnalyticsView):
    analytics_module = "security"

    def get(self, request):
        return Response(get_security_analytics(self.get_filters(request)))


class FraudAnalyticsView(BaseAnalyticsView):
    analytics_module = "fraud"

    def get(self, request):
        return Response(get_fraud_signals(self.get_filters(request)))


class SystemAnalyticsView(BaseAnalyticsView):
    analytics_module = "system"

    def get(self, request):
        return Response(get_system_analytics())


class ExportView(BaseAnalyticsView):
    analytics_module = "exports"

    def get(self, request):
        report_type = request.query_params.get("type", "executive")
        fmt = request.query_params.get("format", "json").lower()
        filters = self.get_filters(request)
        _log_access(request, "export_report", report_type, fmt)
        exporters = {
            "json": export_json,
            "csv": export_csv,
            "xlsx": export_xlsx,
            "pdf": export_pdf,
        }
        exporter = exporters.get(fmt, export_json)
        try:
            return exporter(report_type, filters)
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class ReportPreviewView(BaseAnalyticsView):
    analytics_module = "reports"

    def get(self, request, report_type: str):
        return Response(build_report_data(report_type, self.get_filters(request)))


class AnalyticsEventListView(generics.ListAPIView):
    authentication_classes = [CookieJWTAuthentication, SessionAuthentication]
    permission_classes = [IsAnalyticsUser, AnalyticsModulePermission]
    analytics_module = "behavior"
    serializer_class = AnalyticsEventSerializer

    def get_queryset(self):
        qs = AnalyticsEvent.objects.all()
        category = self.request.query_params.get("category")
        event_type = self.request.query_params.get("event_type")
        if category:
            qs = qs.filter(category=category)
        if event_type:
            qs = qs.filter(event_type=event_type)
        return qs[:500]


class SavedDashboardListCreateView(generics.ListCreateAPIView):
    authentication_classes = [CookieJWTAuthentication, SessionAuthentication]
    permission_classes = [IsAnalyticsUser]
    serializer_class = SavedDashboardSerializer

    def get_queryset(self):
        return SavedDashboard.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
        _log_access(self.request, "create_report", "dashboard", serializer.validated_data.get("slug", ""))


class SavedReportListCreateView(generics.ListCreateAPIView):
    authentication_classes = [CookieJWTAuthentication, SessionAuthentication]
    permission_classes = [IsAnalyticsUser]
    serializer_class = SavedReportSerializer

    def get_queryset(self):
        return SavedReport.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class DailySnapshotListView(generics.ListAPIView):
    authentication_classes = [CookieJWTAuthentication, SessionAuthentication]
    permission_classes = [IsAnalyticsUser, AnalyticsModulePermission]
    analytics_module = "dashboard"
    serializer_class = DailyMetricSnapshotSerializer

    def get_queryset(self):
        return DailyMetricSnapshot.objects.all()[:90]
