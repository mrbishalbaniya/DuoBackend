from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html

from email_service.service import send_test_email
from duo_project.runtime_config import invalidate_integration_cache
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
        "email_relay_secret_status",
        "email_host_password_status",
        "esewa_secret_key_status",
        "webrtc_turn_credential_status",
        "webrtc_turn_secret_status",
        "cloudinary_api_secret_status",
        "firebase_service_account_json_status",
        "openweather_api_key_status",
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
            "WebRTC calls (STUN/TURN)",
            {
                "fields": (
                    "webrtc_stun_urls",
                    "webrtc_turn_url",
                    "webrtc_turn_username",
                    "webrtc_turn_credential_status",
                    "webrtc_turn_credential",
                    "webrtc_turn_secret_status",
                    "webrtc_turn_secret",
                    "webrtc_turn_ttl",
                ),
                "description": (
                    "ICE servers for voice and video calls. Google STUN is free and works for most "
                    "peer-to-peer connections. Add a TURN relay when users are behind strict NAT/firewalls."
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
                    "nodemailer_relay_url",
                    "email_relay_secret_status",
                    "email_relay_secret",
                    "resend_api_key_status",
                    "resend_api_key",
                    "test_email_recipient",
                ),
                "description": (
                    "Nodemailer sends email via the Duo frontend relay (HTTPS). "
                    "Configure SMTP credentials below — same options as "
                    "nodemailer.createTransport({ host, port, secure, auth })."
                ),
            },
        ),
        (
            "Nodemailer SMTP",
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
                "description": (
                    "SMTP transport settings used by Nodemailer. "
                    "Port 587 + STARTTLS (email_use_tls) is typical; use port 465 + SSL for secure: true."
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
        (
            "Firebase Cloud Messaging",
            {
                "fields": (
                    "fcm_enabled",
                    "firebase_project_id",
                    "firebase_api_key",
                    "firebase_auth_domain",
                    "firebase_messaging_sender_id",
                    "firebase_app_id",
                    "fcm_vapid_key",
                    "firebase_service_account_json_status",
                    "firebase_service_account_json",
                ),
                "description": (
                    "Push notifications for new chat messages and matches. "
                    "Create a Firebase web app, enable Cloud Messaging, and upload the service account JSON."
                ),
            },
        ),
        (
            "OpenWeather",
            {
                "fields": (
                    "openweather_api_key_status",
                    "openweather_api_key",
                ),
                "description": (
                    "Live map weather (current conditions, forecast, air quality). "
                    "Values here override OPENWEATHER_API_KEY from environment when set."
                ),
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

    @admin.display(description="Email relay secret")
    def email_relay_secret_status(self, obj):
        return _secret_status_html(obj.email_relay_secret)

    @admin.display(description="SMTP password")
    def email_host_password_status(self, obj):
        return _secret_status_html(obj.email_host_password)

    @admin.display(description="eSewa secret key")
    def esewa_secret_key_status(self, obj):
        return _secret_status_html(obj.esewa_secret_key)

    @admin.display(description="TURN credential")
    def webrtc_turn_credential_status(self, obj):
        return _secret_status_html(obj.webrtc_turn_credential)

    @admin.display(description="TURN shared secret")
    def webrtc_turn_secret_status(self, obj):
        return _secret_status_html(obj.webrtc_turn_secret)

    @admin.display(description="Cloudinary API secret")
    def cloudinary_api_secret_status(self, obj):
        return _secret_status_html(obj.cloudinary_api_secret)

    @admin.display(description="Firebase service account")
    def firebase_service_account_json_status(self, obj):
        return _secret_status_html(obj.firebase_service_account_json)

    @admin.display(description="OpenWeather API key")
    def openweather_api_key_status(self, obj):
        return _secret_status_html(obj.openweather_api_key)

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
        invalidate_integration_cache()
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
