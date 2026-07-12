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
from analytics.services.funnel.analytics import get_funnel_analytics
from analytics.services.kpi.executive import get_executive_dashboard
from analytics.services.matching.analytics import get_matching_analytics
from analytics.services.retention.analytics import get_retention_analytics
from analytics.services.revenue.analytics import get_revenue_analytics
from analytics.services.security.analytics import get_fraud_signals, get_security_analytics
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
    rows = _flatten_dict(data)
    buffer = io.StringIO()
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{report_type}_{_stamp()}.csv"'
    return response


def export_xlsx(report_type: str, filters: dict | None = None) -> HttpResponse:
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise RuntimeError("openpyxl is required for Excel exports") from exc

    data = build_report_data(report_type, filters)
    rows = _flatten_dict(data)
    wb = Workbook()
    ws = wb.active
    ws.title = report_type[:31]
    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h) for h in headers])
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
    pdf.setTitle(f"Duo Analytics — {report_type}")
    y = 800
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, f"Duo Analytics Report: {report_type.title()}")
    y -= 30
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Generated: {timezone.now().isoformat()}")
    y -= 20
    for line in json.dumps(data, indent=2, default=str).splitlines()[:60]:
        if y < 50:
            pdf.showPage()
            y = 800
            pdf.setFont("Helvetica", 9)
        pdf.drawString(50, y, line[:100])
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
