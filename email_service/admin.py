from django.contrib import admin, messages
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from email_service.config import get_email_config
from email_service.admin_forms import AnnouncementForm
from email_service.admin_preview import sample_context
from email_service.constants import EmailEvent, EmailStatus
from email_service.service import send_email
from email_service.triggers import send_user_email
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
    list_display = ("event", "subject", "updated_at", "preview_link")
    fields = ("event", "subject", "text_body", "html_body", "preview_subject", "preview_html", "updated_at")
    readonly_fields = ("updated_at", "preview_subject", "preview_html")
    change_list_template = "admin/email_service/emailtemplate/change_list.html"

    def _render(self, obj):
        # Admin previews use sample data so every variable shows something real.
        return preview_email(
            obj.event,
            get_email_config(),
            obj.subject,
            obj.text_body,
            obj.html_body,
            sample_context=sample_context(obj.event),
        )

    # ── extra admin pages ──
    def get_urls(self):
        custom = [
            path("announce/", self.admin_site.admin_view(self.announce_view), name="email_service_announce"),
            path(
                "<int:pk>/preview/",
                self.admin_site.admin_view(self.full_preview_view),
                name="email_service_emailtemplate_full_preview",
            ),
            path(
                "<int:pk>/send-test/",
                self.admin_site.admin_view(self.send_test_view),
                name="email_service_emailtemplate_send_test",
            ),
        ]
        return custom + super().get_urls()

    def full_preview_view(self, request, pk):
        obj = get_object_or_404(EmailTemplate, pk=pk)
        return HttpResponse(self._render(obj)["html_body"])

    def send_test_view(self, request, pk):
        obj = get_object_or_404(EmailTemplate, pk=pk)
        change_url = reverse("admin:email_service_emailtemplate_change", args=[pk])
        if request.method != "POST":
            return redirect(change_url)
        to = (request.user.email or "").strip()
        if not to:
            messages.error(request, "Add an email address to your admin user first.")
            return redirect(change_url)
        rendered = self._render(obj)
        try:
            send_email(
                event=obj.event,
                to=to,
                subject=f"[Test] {rendered['subject']}",
                message=rendered["text_body"],
                html_message=rendered["html_body"],
                fail_silently=False,
            )
            messages.success(request, f"Test email sent to {to}.")
        except Exception as exc:
            messages.error(request, f"Could not send test email: {exc}")
        return redirect(change_url)

    def announce_view(self, request):
        form = AnnouncementForm(request.POST or None)
        context = {
            **self.admin_site.each_context(request),
            "title": "Send announcement email",
            "form": form,
            "opts": self.model._meta,
            "recipient_counts": {key: AnnouncementForm.audience_queryset(key).count() for key, _ in AnnouncementForm.AUDIENCES},
        }
        if request.method == "POST" and form.is_valid():
            data = form.cleaned_data
            email_context = {
                "title": data["title"],
                "message": data["message"],
                "cta_label": data.get("button_label") or "",
                "cta_url": data.get("button_url") or "",
            }
            if "send_test" in request.POST:
                to = (request.user.email or "").strip()
                if not to:
                    messages.error(request, "Add an email address to your admin user to send a test.")
                else:
                    send_email(
                        event=EmailEvent.ADMIN_ANNOUNCEMENT,
                        to=to,
                        context={"user_name": request.user.get_username(), **email_context},
                        fail_silently=True,
                    )
                    messages.success(request, f"Test sent to {to}. Check it, then send to everyone.")
                context["form"] = form
                return TemplateResponse(request, "admin/email_service/announce.html", context)

            users = AnnouncementForm.audience_queryset(data["audience"])
            sent = 0
            for user in users.iterator():
                send_user_email(user, EmailEvent.ADMIN_ANNOUNCEMENT, dict(email_context))
                sent += 1
            messages.success(request, f"Announcement queued for {sent} user(s).")
            return redirect("admin:email_service_emailtemplate_changelist")
        return TemplateResponse(request, "admin/email_service/announce.html", context)

    # ── list + form widgets ──
    @admin.display(description="Preview")
    def preview_link(self, obj):
        url = reverse("admin:email_service_emailtemplate_full_preview", args=[obj.pk])
        return format_html('<a href="{}" target="_blank" rel="noopener">Open preview ↗</a>', url)

    @admin.display(description="Preview subject")
    def preview_subject(self, obj):
        if not obj or not obj.pk:
            return "—"
        return self._render(obj)["subject"]

    @admin.display(description="Preview HTML")
    def preview_html(self, obj):
        if not obj or not obj.pk:
            return "Save the template to see a preview."
        rendered = self._render(obj)
        return mark_safe(render_to_string(
            "admin/email_service/emailtemplate/preview_field.html",
            {
                "html": rendered["html_body"],
                "text": rendered["text_body"],
                "full_url": reverse("admin:email_service_emailtemplate_full_preview", args=[obj.pk]),
                "send_test_url": reverse("admin:email_service_emailtemplate_send_test", args=[obj.pk]),
            },
        ))


@admin.register(EmailEventSetting)
class EmailEventSettingAdmin(admin.ModelAdmin):
    list_display = ("event", "enabled", "subject_template", "updated_at")
    list_editable = ("enabled",)
    fields = ("event", "enabled", "subject_template", "updated_at")
    readonly_fields = ("updated_at",)
