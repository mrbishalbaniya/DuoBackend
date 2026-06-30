from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from email_service.service import send_test_email
from site_config.forms import SECRET_FIELDS, SiteSettingsForm
from site_config.models import SiteSettings


def _secret_status_html(value: str) -> str:
    if (value or "").strip():
        return format_html(
            '<span class="duo-secret-badge duo-secret-badge--saved">'
            '<i class="fas fa-lock" aria-hidden="true"></i> Saved (encrypted)</span>'
        )
    return format_html(
        '<span class="duo-secret-badge duo-secret-badge--empty">'
        '<i class="fas fa-unlock" aria-hidden="true"></i> Not set yet</span>'
    )


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    form = SiteSettingsForm
    readonly_fields = (
        "updated_at",
        "google_client_secret_status",
        "resend_api_key_status",
        "brevo_api_key_status",
        "email_host_password_status",
        "esewa_secret_key_status",
        "cloudinary_api_secret_status",
    )

    fieldsets = (
        (
            "Google sign-in",
            {
                "fields": (
                    "google_client_id",
                    "google_client_secret_status",
                    "google_client_secret",
                    "google_redirect_uri",
                    "google_allowed_redirect_uris",
                ),
                "description": (
                    "Configure Google OAuth for web and mobile login. "
                    "Values here override environment variables when set."
                ),
            },
        ),
        (
            "Email delivery",
            {
                "fields": (
                    "email_delivery",
                    "email_from_name",
                    "default_from_email",
                    "brevo_api_key_status",
                    "brevo_api_key",
                    "resend_api_key_status",
                    "resend_api_key",
                    "test_email_recipient",
                ),
                "description": (
                    "Brevo SMTP is the default provider (smtp-relay.brevo.com:587, TLS). "
                    "On Render free tier, SMTP ports may be blocked — keep a Brevo API key "
                    "configured for automatic HTTPS fallback."
                ),
            },
        ),
        (
            "Brevo SMTP",
            {
                "fields": (
                    "email_host",
                    "email_port",
                    "email_use_tls",
                    "email_use_ssl",
                    "email_host_user",
                    "email_host_password_status",
                    "email_host_password",
                ),
            },
        ),
        (
            "Email branding",
            {
                "fields": (
                    "email_brand_logo_url",
                    "email_brand_primary_color",
                    "email_footer_text",
                    "email_social_links",
                ),
                "description": "Used by HTML templates in Email service → Email templates.",
            },
        ),
        (
            "eSewa payments",
            {
                "fields": (
                    "esewa_product_code",
                    "esewa_secret_key_status",
                    "esewa_secret_key",
                    "esewa_form_url",
                    "esewa_status_url",
                    "esewa_success_url",
                    "esewa_failure_url",
                ),
                "description": "Premium subscription payments via eSewa.",
            },
        ),
        (
            "Cloudinary media",
            {
                "fields": (
                    "cloudinary_cloud_name",
                    "cloudinary_api_key",
                    "cloudinary_api_secret_status",
                    "cloudinary_api_secret",
                    "cloudinary_upload_preset",
                    "cloudinary_profile_folder",
                    "cloudinary_chat_folder",
                    "cloudinary_verification_folder",
                ),
                "description": "Profile photos, chat media, and verification selfies.",
            },
        ),
        ("Meta", {"fields": ("updated_at",)}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "send-test-email/",
                self.admin_site.admin_view(self.send_test_email_view),
                name="site_config_sitesettings_send_test_email",
            ),
        ]
        return custom + urls

    def send_test_email_view(self, request):
        if request.method != "POST":
            return HttpResponseRedirect(reverse("admin:site_config_sitesettings_change", args=[1]))

        recipient = (request.POST.get("test_email_recipient") or "").strip()
        if not recipient:
            messages.error(request, "Enter a test email recipient address first.")
        else:
            ok, detail = send_test_email(recipient)
            if ok:
                messages.success(request, detail)
            else:
                messages.error(request, f"Test email failed: {detail}")

        return HttpResponseRedirect(reverse("admin:site_config_sitesettings_change", args=[1]))

    @admin.display(description="Google client secret")
    def google_client_secret_status(self, obj):
        return _secret_status_html(obj.google_client_secret)

    @admin.display(description="Resend API key")
    def resend_api_key_status(self, obj):
        return _secret_status_html(obj.resend_api_key)

    @admin.display(description="Brevo API key")
    def brevo_api_key_status(self, obj):
        return _secret_status_html(obj.brevo_api_key)

    @admin.display(description="SMTP password")
    def email_host_password_status(self, obj):
        return _secret_status_html(obj.email_host_password)

    @admin.display(description="eSewa secret key")
    def esewa_secret_key_status(self, obj):
        return _secret_status_html(obj.esewa_secret_key)

    @admin.display(description="Cloudinary API secret")
    def cloudinary_api_secret_status(self, obj):
        return _secret_status_html(obj.cloudinary_api_secret)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = SiteSettings.get_solo()
        url = reverse("admin:site_config_sitesettings_change", args=[obj.pk])
        return HttpResponseRedirect(url)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["title"] = "Integration settings"
        extra_context["test_email_url"] = reverse("admin:site_config_sitesettings_send_test_email")
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def save_model(self, request, obj, form, change):
        form.save()
        updated_secrets = [
            name
            for name in SECRET_FIELDS
            if (form.cleaned_data.get(name) or "").strip()
        ]
        if updated_secrets:
            messages.success(
                request,
                f"Saved integration settings. Updated secrets: {', '.join(updated_secrets)}.",
            )
        else:
            messages.success(
                request,
                "Saved integration settings. Existing secrets were kept unchanged.",
            )

    def response_change(self, request, obj):
        return HttpResponseRedirect(request.path)
