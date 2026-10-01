"""Report export service — CSV, JSON, Excel, PDF."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from django.http import HttpResponse
from django.utils import timezone

from analytics.services.behavior.analytics import get_behavior_analytics
from analytics.services.chat.analytics import get_chat_analytics
from analytics.services.forecast.analytics import get_forecast_analytics
from analytics.services.funnel.analytics import get_funnel_analytics
from analytics.services.kpi.executive import get_executive_dashboard
from analytics.services.maps.analytics import get_map_analytics
from analytics.services.matching.analytics import get_matching_analytics
from analytics.services.retention.analytics import get_retention_analytics
from analytics.services.revenue.analytics import get_revenue_analytics
from analytics.services.security.analytics import get_fraud_signals, get_security_analytics
from analytics.services.system.analytics import get_system_analytics
from analytics.services.users.analytics import get_user_analytics


REPORT_BUILDERS = {
    "executive": get_executive_dashboard,
    "revenue": get_revenue_analytics,
    "users": get_user_analytics,
    "matching": get_matching_analytics,
    "chat": get_chat_analytics,
    "funnel": get_funnel_analytics,
    "retention": get_retention_analytics,
    "security": get_security_analytics,
    "fraud": get_fraud_signals,
    "behavior": get_behavior_analytics,
    "maps": get_map_analytics,
    "forecast": get_forecast_analytics,
    "system": lambda _filters=None: get_system_analytics(),
}


def build_report_data(report_type: str, filters: dict | None = None) -> dict:
    builder = REPORT_BUILDERS.get(report_type, get_executive_dashboard)
    return builder(filters or {})


def export_json(report_type: str, filters: dict | None = None) -> HttpResponse:
    data = build_report_data(report_type, filters)
    response = HttpResponse(
        json.dumps(data, indent=2, default=str),
        content_type="application/json",
    )
    response["Content-Disposition"] = f'attachment; filename="{report_type}_{_stamp()}.json"'
    return response


def export_csv(report_type: str, filters: dict | None = None) -> HttpResponse:
    data = build_report_data(report_type, filters)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["metric", "value"])
    writer.writerows(_metric_rows(data))
    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{report_type}_{_stamp()}.csv"'
    return response


def export_xlsx(report_type: str, filters: dict | None = None) -> HttpResponse:
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise RuntimeError("openpyxl is required for Excel exports") from exc

    data = build_report_data(report_type, filters)
    wb = Workbook()
    ws = wb.active
    ws.title = report_type[:31]
    ws.append(["metric", "value"])
    for key, value in _metric_rows(data):
        ws.append([key, value if isinstance(value, (int, float)) or value is None else str(value)])
    ws.column_dimensions["A"].width = 48
    ws.column_dimensions["B"].width = 24
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{report_type}_{_stamp()}.xlsx"'
    return response


def export_pdf(report_type: str, filters: dict | None = None) -> HttpResponse:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError("reportlab is required for PDF exports") from exc

    data = build_report_data(report_type, filters)
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(f"Duo Analytics - {report_type}")
    y = 800
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, f"Duo Analytics Report: {report_type.title()}")
    y -= 22
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Generated: {timezone.now().strftime('%Y-%m-%d %H:%M %Z')}")
    y -= 24
    section = None
    for key, value in _metric_rows(data):
        top = key.split(".", 1)[0]
        if top != section:
            section = top
            if y < 80:
                pdf.showPage()
                y = 800
            y -= 6
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(50, y, top.replace("_", " ").title())
            y -= 16
        if y < 50:
            pdf.showPage()
            y = 800
        pdf.setFont("Helvetica", 9)
        label = key.split(".", 1)[1] if "." in key else key
        pdf.drawString(60, y, label.replace("_", " ")[:70])
        pdf.drawString(360, y, str(value)[:45])
        y -= 12
    pdf.save()
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{report_type}_{_stamp()}.pdf"'
    return response


def _stamp() -> str:
    return timezone.now().strftime("%Y%m%d_%H%M%S")


def _flatten_dict(data: Any, prefix: str = "") -> list[dict]:
    rows = []
    if isinstance(data, dict):
        flat = {}
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, (dict, list)):
                flat[full_key] = json.dumps(value, default=str)
            else:
                flat[full_key] = value
        rows.append(flat)
    return rows


def _metric_rows(data: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten nested report data into (dotted.key, value) pairs."""
    rows: list[tuple[str, Any]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            rows.extend(_metric_rows(value, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(data, list):
        for i, value in enumerate(data):
            rows.extend(_metric_rows(value, f"{prefix}[{i}]"))
    else:
        rows.append((prefix, data))
    return rows
