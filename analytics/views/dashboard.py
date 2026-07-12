"""Analytics admin dashboard view."""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from analytics.permissions import user_can_access_module
from analytics.services.kpi.executive import get_executive_dashboard


@staff_member_required
def analytics_dashboard_view(request):
    if not user_can_access_module(request.user, "dashboard"):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("You do not have permission to view analytics.")

    dashboard_data = get_executive_dashboard()
    return render(
        request,
        "analytics/dashboard.html",
        {
            "dashboard_data": dashboard_data,
            "title": "Executive Analytics Dashboard",
        },
    )
