"""Django admin integration for Celery task results."""

from __future__ import annotations

from django.contrib import admin, messages
from django.utils.html import format_html

try:
    from django_celery_results.models import TaskResult
except ImportError:
    TaskResult = None  # type: ignore[misc, assignment]


if TaskResult is not None:
    try:
        admin.site.unregister(TaskResult)
    except admin.sites.NotRegistered:
        pass

    @admin.register(TaskResult)
    class TaskResultAdmin(admin.ModelAdmin):
        list_display = (
            "task_id_short",
            "task_name",
            "status_colored",
            "date_created",
            "date_done",
            "worker",
        )
        list_filter = ("status", "task_name", "date_done")
        search_fields = ("task_id", "task_name", "traceback")
        readonly_fields = (
            "task_id",
            "task_name",
            "task_args",
            "task_kwargs",
            "status",
            "worker",
            "content_type",
            "content_encoding",
            "result",
            "date_created",
            "date_done",
            "traceback",
            "meta",
        )
        ordering = ("-date_done",)
        actions = ["retry_failed_tasks"]

        @admin.display(description="Task ID")
        def task_id_short(self, obj: TaskResult) -> str:
            return f"{obj.task_id[:12]}…"

        @admin.display(description="Status")
        def status_colored(self, obj: TaskResult) -> str:
            colors = {
                "SUCCESS": "#28a745",
                "FAILURE": "#dc3545",
                "PENDING": "#ffc107",
                "STARTED": "#17a2b8",
                "RETRY": "#fd7e14",
            }
            color = colors.get(obj.status, "#6c757d")
            return format_html('<span style="color:{};font-weight:600;">{}</span>', color, obj.status)

        @admin.action(description="Retry selected failed tasks")
        def retry_failed_tasks(self, request, queryset):
            import json

            from duo_project.celery import app

            retried = 0
            for row in queryset.filter(status="FAILURE"):
                try:
                    args = json.loads(row.task_args) if row.task_args else []
                    kwargs = json.loads(row.task_kwargs) if row.task_kwargs else {}
                    app.send_task(row.task_name, args=args, kwargs=kwargs)
                    retried += 1
                except Exception as exc:
                    self.message_user(
                        request,
                        f"Retry failed for {row.task_id}: {exc}",
                        level=messages.ERROR,
                    )
            if retried:
                self.message_user(
                    request,
                    f"Re-queued {retried} failed task(s).",
                    level=messages.SUCCESS,
                )
