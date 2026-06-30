from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from email_service.config import get_email_config
from email_service.constants import EmailStatus
from email_service.models import EmailEventSetting, EmailLog, EmailTemplate
from email_service.rendering import preview_email


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "event",
        "recipient",
        "subject",
        "provider",
        "status",
        "attempt_count",
    )
    list_filter = ("status", "provider", "event", "created_at")
    search_fields = ("recipient", "subject", "error_message")
    readonly_fields = (
        "event",
        "recipient",
        "subject",
        "provider",
        "status",
        "attempt_count",
        "error_message",
        "provider_message_id",
        "created_at",
    )
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        stats = EmailLog.objects.values("status").annotate(total=Count("id"))
        counts = {row["status"]: row["total"] for row in stats}
        extra_context["email_stats"] = {
            "sent": counts.get(EmailStatus.SENT, 0),
            "delivered": counts.get(EmailStatus.DELIVERED, 0),
            "failed": counts.get(EmailStatus.FAILED, 0),
            "queued": counts.get(EmailStatus.QUEUED, 0),
            "retried": counts.get(EmailStatus.RETRIED, 0),
            "total": sum(counts.values()),
        }
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("event", "subject", "updated_at")
    fields = ("event", "subject", "text_body", "html_body", "preview_subject", "preview_html", "updated_at")
    readonly_fields = ("updated_at", "preview_subject", "preview_html")

    @admin.display(description="Preview subject")
    def preview_subject(self, obj):
        if not obj or not obj.pk:
            return "—"
        preview = preview_email(obj.event, get_email_config(), obj.subject, obj.text_body, obj.html_body)
        return preview["subject"]

    @admin.display(description="Preview HTML")
    def preview_html(self, obj):
        if not obj or not obj.pk:
            return "—"
        preview = preview_email(obj.event, get_email_config(), obj.subject, obj.text_body, obj.html_body)
        return format_html(
            '<iframe srcdoc="{}" style="width:100%;min-height:360px;border:1px solid #ddd;border-radius:8px;"></iframe>',
            preview["html_body"].replace('"', "&quot;"),
        )


@admin.register(EmailEventSetting)
class EmailEventSettingAdmin(admin.ModelAdmin):
    list_display = ("event", "enabled", "subject_template", "updated_at")
    list_editable = ("enabled",)
    fields = ("event", "enabled", "subject_template", "updated_at")
    readonly_fields = ("updated_at",)
