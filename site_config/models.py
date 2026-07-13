from django.db import models


class SiteSettings(models.Model):
    """Singleton integration settings editable from Django admin."""

    SINGLETON_PK = 1

    # Google OAuth
    google_client_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="OAuth 2.0 Client ID from Google Cloud Console.",
    )
    google_client_secret = models.CharField(
        max_length=255,
        blank=True,
        help_text="OAuth 2.0 Client secret. Leave blank when saving to keep the current value.",
    )
    google_redirect_uri = models.URLField(
        max_length=500,
        blank=True,
        help_text="Backend callback URL, e.g. https://duobackend.onrender.com/api/auth/google/callback/",
    )
    google_allowed_redirect_uris = models.TextField(
        blank=True,
        help_text="Comma-separated redirect URIs allowed for token exchange (include web and mobile callbacks).",
    )

    # Email delivery (Nodemailer-compatible SMTP — https://nodemailer.com/)
    EMAIL_DELIVERY_NODEMAILER = "nodemailer"
    EMAIL_DELIVERY_SMTP = "smtp"
    EMAIL_DELIVERY_RESEND = "resend"
    EMAIL_DELIVERY_CHOICES = [
        (EMAIL_DELIVERY_NODEMAILER, "Nodemailer (recommended — HTTPS relay via frontend)"),
        (EMAIL_DELIVERY_SMTP, "SMTP direct (Django — use when relay is unavailable)"),
        (EMAIL_DELIVERY_RESEND, "Resend API"),
    ]

    email_delivery = models.CharField(
        max_length=16,
        choices=EMAIL_DELIVERY_CHOICES,
        default=EMAIL_DELIVERY_NODEMAILER,
        help_text="Nodemailer sends via the Duo frontend relay using the SMTP settings below.",
    )
    nodemailer_relay_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Optional relay URL (default: FRONTEND_URL/api/internal/email).",
    )
    email_relay_secret = models.CharField(
        max_length=255,
        blank=True,
        help_text="Shared secret for the Nodemailer relay. Leave blank when saving to keep the current value.",
    )
    resend_api_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="Resend API key (re_...). Leave blank when saving to keep the current value.",
    )
    brevo_api_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="Deprecated — no longer used. Leave blank.",
    )

    # SMTP (Nodemailer transport options)
    email_host = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="SMTP host (Nodemailer: transport.host), e.g. smtp.gmail.com or smtp.sendgrid.net.",
    )
    email_port = models.PositiveIntegerField(default=587, blank=True, null=True)
    email_use_tls = models.BooleanField(default=True, blank=True, null=True)
    email_use_ssl = models.BooleanField(
        default=False,
        blank=True,
        null=True,
        help_text="Use SSL on connect (port 465). Leave off for STARTTLS on port 587.",
    )
    email_host_user = models.CharField(
        max_length=255,
        blank=True,
        help_text="SMTP username (Nodemailer: transport.auth.user).",
    )
    email_host_password = models.CharField(
        max_length=255,
        blank=True,
        help_text="SMTP password or app password. Leave blank when saving to keep the current value.",
    )
    email_from_name = models.CharField(
        max_length=128,
        blank=True,
        default="SajiloWork",
        help_text="Default sender display name.",
    )
    default_from_email = models.CharField(
        max_length=255,
        blank=True,
        help_text='Verified sender, e.g. "SajiloWork <noreply@yourdomain.com>".',
    )
    email_brand_logo_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Logo URL for HTML email templates.",
    )
    email_brand_primary_color = models.CharField(
        max_length=16,
        blank=True,
        default="#6366f1",
        help_text="Brand accent color for email templates (hex).",
    )
    email_footer_text = models.CharField(
        max_length=500,
        blank=True,
        default="© SajiloWork. All rights reserved.",
    )
    email_social_links = models.TextField(
        blank=True,
        help_text="Optional footer links (one per line: Label|https://url).",
    )

    # eSewa
    esewa_product_code = models.CharField(
        max_length=64,
        blank=True,
        help_text="Merchant product code (EPAYTEST for sandbox).",
    )
    esewa_secret_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="HMAC secret for payment signatures. Leave blank when saving to keep the current value.",
    )
    esewa_form_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="eSewa payment form URL (sandbox or production).",
    )
    esewa_status_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="eSewa transaction status API base URL.",
    )
    esewa_success_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Backend success callback, e.g. https://duobackend.onrender.com/api/subscriptions/esewa/success/",
    )
    esewa_failure_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Backend failure callback.",
    )

    # Cloudinary
    cloudinary_cloud_name = models.CharField(max_length=128, blank=True)
    cloudinary_api_key = models.CharField(max_length=128, blank=True)
    cloudinary_api_secret = models.CharField(
        max_length=255,
        blank=True,
        help_text="Leave blank when saving to keep the current value.",
    )
    cloudinary_upload_preset = models.CharField(max_length=128, blank=True)
    cloudinary_profile_folder = models.CharField(
        max_length=255,
        blank=True,
        default="duo/profile_photos",
    )
    cloudinary_chat_folder = models.CharField(
        max_length=255,
        blank=True,
        default="duo/chat_media",
    )
    cloudinary_verification_folder = models.CharField(
        max_length=255,
        blank=True,
        default="duo/verification_selfies",
    )

    # OpenWeather (live map weather)
    openweather_api_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="OpenWeather API key from openweathermap.org/api_keys. Leave blank when saving to keep the current value.",
    )

    # Firebase Cloud Messaging (push notifications)
    fcm_enabled = models.BooleanField(
        default=False,
        help_text="Enable web and mobile push notifications via Firebase Cloud Messaging.",
    )
    firebase_project_id = models.CharField(
        max_length=128,
        blank=True,
        help_text="Firebase project ID from Project settings.",
    )
    firebase_api_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="Web API key from Firebase Console → Project settings → Your apps.",
    )
    firebase_auth_domain = models.CharField(
        max_length=255,
        blank=True,
        help_text="e.g. your-project.firebaseapp.com",
    )
    firebase_messaging_sender_id = models.CharField(
        max_length=64,
        blank=True,
        help_text="Messaging sender ID (numeric) from Firebase web app config.",
    )
    firebase_app_id = models.CharField(
        max_length=128,
        blank=True,
        help_text="Firebase web app ID (1:...:web:...).",
    )
    firebase_android_app_id = models.CharField(
        max_length=128,
        blank=True,
        help_text="Firebase Android app ID (1:...:android:...). Required for DuoMobile push.",
    )
    firebase_ios_app_id = models.CharField(
        max_length=128,
        blank=True,
        help_text="Firebase iOS app ID (1:...:ios:...). Required for DuoMobile push on iOS.",
    )
    fcm_vapid_key = models.CharField(
        max_length=512,
        blank=True,
        help_text="Web Push certificate public key from Firebase → Cloud Messaging → Web configuration.",
    )
    firebase_service_account_json = models.TextField(
        blank=True,
        help_text=(
            "Service account JSON with Firebase Cloud Messaging Admin role. "
            "Leave blank when saving to keep the current value."
        ),
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Integration settings"
        verbose_name_plural = "Integration settings"

    def __str__(self) -> str:
        return "Integration settings"

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _created = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        return obj
