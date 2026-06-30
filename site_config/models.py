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

    # Email delivery
    EMAIL_DELIVERY_SMTP = "smtp"
    EMAIL_DELIVERY_RESEND = "resend"
    EMAIL_DELIVERY_CHOICES = [
        (EMAIL_DELIVERY_SMTP, "SMTP (local dev / paid Render)"),
        (EMAIL_DELIVERY_RESEND, "Resend API (required on Render free tier)"),
    ]

    email_delivery = models.CharField(
        max_length=16,
        choices=EMAIL_DELIVERY_CHOICES,
        default=EMAIL_DELIVERY_RESEND,
        help_text=(
            "Render free tier blocks SMTP ports 587/465. Use Resend on production "
            "or upgrade Render to a paid plan for Gmail SMTP."
        ),
    )
    resend_api_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="Resend API key (re_...). Leave blank when saving to keep the current value.",
    )

    # SMTP
    email_host = models.CharField(max_length=255, blank=True, default="smtp.gmail.com")
    email_port = models.PositiveIntegerField(default=587, blank=True, null=True)
    email_use_tls = models.BooleanField(default=True, blank=True, null=True)
    email_host_user = models.CharField(max_length=255, blank=True)
    email_host_password = models.CharField(
        max_length=255,
        blank=True,
        help_text="SMTP password or app password. Leave blank when saving to keep the current value.",
    )
    default_from_email = models.CharField(
        max_length=255,
        blank=True,
        help_text='Sender address, e.g. "Duo <noreply@yourdomain.com>".',
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
