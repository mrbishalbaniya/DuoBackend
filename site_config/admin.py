from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html

from site_config.forms import SECRET_FIELDS, SiteSettingsForm
from site_config.models import SiteSettings


def _secret_status_html(value: str) -> str:
    if (value or "").strip():
        return format_html(
            '<span class="duo-secret-badge duo-secret-badge--saved">'
            '<i class="fas fa-lock" aria-hidden="true"></i> Saved (hidden for security)</span>'
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
            "Email (SMTP)",
            {
                "fields": (
                    "email_host",
                    "email_port",
                    "email_use_tls",
                    "email_host_user",
                    "email_host_password_status",
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

    @admin.display(description="Google client secret")
    def google_client_secret_status(self, obj):
        return _secret_status_html(obj.google_client_secret)

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
        # save_model already shows the success message.
        return HttpResponseRedirect(request.path)
