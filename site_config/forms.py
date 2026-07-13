from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from duo_project.secret_fields import decrypt_secret, encrypt_secret
from email_service.config import EmailConfig
from email_service.credentials import is_placeholder, is_valid_resend_api_key
from email_service.service import test_smtp_configuration
from site_config.models import SiteSettings
from site_config.widgets import RevealablePasswordInput

SECRET_FIELDS = (
    "google_client_secret",
    "email_host_password",
    "email_relay_secret",
    "resend_api_key",
    "esewa_secret_key",
    "cloudinary_api_secret",
    "openweather_api_key",
    "firebase_service_account_json",
    "webrtc_turn_credential",
    "webrtc_turn_secret",
)
LONG_SECRET_FIELDS = ("firebase_service_account_json",)


class SiteSettingsForm(forms.ModelForm):
    test_email_recipient = forms.EmailField(
        required=False,
        label="Test email recipient",
        help_text="Enter an address and click “Send test email” below to verify delivery.",
    )

    class Meta:
        model = SiteSettings
        exclude = ("id", "brevo_api_key")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = self.instance

        for name in SECRET_FIELDS:
            field = self.fields.get(name)
            if not field:
                continue

            stored = ""
            if instance and instance.pk:
                stored = (getattr(instance, name, "") or "").strip()

            configured = bool(stored)
            if name in LONG_SECRET_FIELDS:
                field.widget = forms.Textarea(
                    attrs={
                        "rows": 10,
                        "class": "vLargeTextField",
                        "autocomplete": "off",
                        "placeholder": (
                            "Saved — leave blank to keep, or paste new JSON"
                            if configured
                            else "Paste service account JSON, then click Save"
                        ),
                    }
                )
            else:
                field.widget = RevealablePasswordInput(configured=configured)
            field.required = False
            field.help_text = (
                "Encrypted in database. Click Show to view, or type a new value to replace it."
                if configured and name not in LONG_SECRET_FIELDS
                else (
                    "Encrypted in database. Leave blank when saving to keep the current JSON."
                    if configured
                    else "Enter the secret value, then click Save at the bottom of the page."
                )
            )

    def _merged_secret(self, name: str) -> str:
        new_value = (self.cleaned_data.get(name) or "").strip()
        if new_value:
            return new_value
        previous = SiteSettings.objects.filter(pk=SiteSettings.SINGLETON_PK).first()
        if previous:
            return decrypt_secret((getattr(previous, name, "") or "").strip())
        return ""

    def _email_config_from_cleaned(self, cleaned, *, delivery: str) -> EmailConfig:
        return EmailConfig(
            delivery=delivery,
            host=(cleaned.get("email_host") or "").strip(),
            port=int(cleaned.get("email_port") or 587),
            use_tls=bool(cleaned.get("email_use_tls") if cleaned.get("email_use_tls") is not None else True),
            use_ssl=bool(cleaned.get("email_use_ssl") if cleaned.get("email_use_ssl") is not None else False),
            username=(cleaned.get("email_host_user") or "").strip(),
            password=self._merged_secret("email_host_password").replace(" ", ""),
            nodemailer_relay_url=(cleaned.get("nodemailer_relay_url") or "").strip(),
            email_relay_secret=self._merged_secret("email_relay_secret"),
            resend_api_key=self._merged_secret("resend_api_key"),
            from_email=(cleaned.get("default_from_email") or "").strip(),
            from_name=(cleaned.get("email_from_name") or "SajiloWork").strip(),
            brand_logo_url=(cleaned.get("email_brand_logo_url") or "").strip(),
            brand_primary_color=(cleaned.get("email_brand_primary_color") or "#6366f1").strip(),
            footer_text=(cleaned.get("email_footer_text") or "").strip(),
            social_links=(cleaned.get("email_social_links") or "").strip(),
            smtp_timeout=15,
        )

    def clean(self):
        cleaned = super().clean()
        delivery = (cleaned.get("email_delivery") or SiteSettings.EMAIL_DELIVERY_NODEMAILER).strip().lower()

        if delivery == SiteSettings.EMAIL_DELIVERY_RESEND:
            resend_key = self._merged_secret("resend_api_key")
            if not resend_key or not is_valid_resend_api_key(resend_key):
                raise ValidationError("Resend API key is required when delivery is set to Resend.")
            return cleaned

        host = (cleaned.get("email_host") or "").strip()
        host_user = (cleaned.get("email_host_user") or "").strip()
        password = self._merged_secret("email_host_password")
        if not host or not host_user or not password or is_placeholder(password):
            raise ValidationError(
                "SMTP host, username, and password are required for Nodemailer/SMTP delivery."
            )

        if delivery == SiteSettings.EMAIL_DELIVERY_NODEMAILER:
            relay_secret = self._merged_secret("email_relay_secret")
            env_secret = getattr(settings, "EMAIL_RELAY_SECRET", "") or ""
            if (not relay_secret or is_placeholder(relay_secret)) and not env_secret.strip():
                raise ValidationError(
                    "Email relay secret is required for Nodemailer delivery "
                    "(set in admin or EMAIL_RELAY_SECRET env)."
                )

        if delivery == SiteSettings.EMAIL_DELIVERY_SMTP:
            config = self._email_config_from_cleaned(cleaned, delivery="smtp")
            ok, message = test_smtp_configuration(config)
            if not ok:
                raise ValidationError(f"SMTP validation failed: {message}")

        stun_urls = (cleaned.get("webrtc_stun_urls") or "").strip()
        if stun_urls:
            for url in (part.strip() for part in stun_urls.split(",") if part.strip()):
                if not url.lower().startswith(("stun:", "turn:", "turns:")):
                    raise ValidationError(
                        f"Invalid STUN/TURN URL '{url}'. URLs must start with stun:, turn:, or turns:."
                    )

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.pk = SiteSettings.SINGLETON_PK

        previous = SiteSettings.objects.filter(pk=SiteSettings.SINGLETON_PK).first()
        if previous:
            for name in SECRET_FIELDS:
                new_value = (self.cleaned_data.get(name) or "").strip()
                if not new_value:
                    setattr(instance, name, getattr(previous, name))
                else:
                    setattr(instance, name, encrypt_secret(new_value))

        if commit:
            instance.save()
            self.save_m2m()
        return instance
