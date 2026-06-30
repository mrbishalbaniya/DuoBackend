from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import reverse

from site_config.forms import SiteSettingsForm
from site_config.models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    form = SiteSettingsForm
    readonly_fields = ("updated_at",)

    class Media:
        css = {"all": ("site_config/css/revealable_password.css",)}

    fieldsets = (
        (
            "Google sign-in",
            {
                "fields": (
                    "google_client_id",
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
            "Email (SMTP)",
            {
                "fields": (
                    "email_host",
                    "email_port",
                    "email_use_tls",
                    "email_host_user",
                    "email_host_password",
                    "default_from_email",
                ),
                "description": "Used for registration OTP and password reset emails.",
            },
        ),
        (
            "eSewa payments",
            {
                "fields": (
                    "esewa_product_code",
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
        extra_context["subtitle"] = (
            "Secret fields look empty after saving for security. "
            "A green note means a value is already stored."
        )
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def response_change(self, request, obj):
        messages.success(
            request,
            "Integration settings saved. Secret fields stay hidden for security; "
            "green notes confirm stored values.",
        )
        return super().response_change(request, obj)
