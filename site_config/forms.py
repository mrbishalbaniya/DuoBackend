from django import forms
from django.core.exceptions import ValidationError

from duo_project.secret_fields import decrypt_secret, encrypt_secret
from email_service.credentials import is_placeholder, is_valid_brevo_api_key, is_valid_brevo_smtp_key
from email_service.config import EmailConfig
from email_service.service import test_smtp_configuration
from site_config.models import SiteSettings
from site_config.widgets import RevealablePasswordInput

SECRET_FIELDS = (
    "google_client_secret",
    "email_host_password",
    "resend_api_key",
    "brevo_api_key",
    "esewa_secret_key",
    "cloudinary_api_secret",
)


class SiteSettingsForm(forms.ModelForm):
    test_email_recipient = forms.EmailField(
        required=False,
        label="Test email recipient",
        help_text="Enter an address and click “Send test email” below to verify delivery.",
    )

    class Meta:
        model = SiteSettings
        exclude = ("id",)

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
            field.widget = RevealablePasswordInput(configured=configured)
            field.required = False
            field.help_text = (
                "Encrypted in database. Click Show to view, or type a new value to replace it."
                if configured
                else "Enter the secret value, then click Save at the bottom of the page."
            )

    def _merged_secret(self, name: str) -> str:
        new_value = (self.cleaned_data.get(name) or "").strip()
        if new_value:
            return new_value
        previous = SiteSettings.objects.filter(pk=SiteSettings.SINGLETON_PK).first()
        if previous:
            return decrypt_secret((getattr(previous, name, "") or "").strip())
        return ""

    def clean(self):
        cleaned = super().clean()
        delivery = (cleaned.get("email_delivery") or "smtp").strip().lower()

        brevo_key = self._merged_secret("brevo_api_key")
        if brevo_key and not is_valid_brevo_api_key(brevo_key):
            raise ValidationError(
                "Brevo API key is invalid. Use a real key from Brevo → SMTP & API "
                "(starts with xkeysib-, not a placeholder)."
            )

        if delivery == SiteSettings.EMAIL_DELIVERY_SMTP:
            host_user = (cleaned.get("email_host_user") or "").strip()
            password = self._merged_secret("email_host_password")
            host = (cleaned.get("email_host") or "smtp-relay.brevo.com").strip()
            if not host_user or not password:
                raise ValidationError(
                    "Brevo SMTP requires SMTP login and SMTP key when delivery is set to SMTP."
                )
            if "@" not in host_user:
                raise ValidationError(
                    "Brevo SMTP login must be copied from the Brevo SMTP tab (includes @), "
                    "not an app name or username."
                )
            if "brevo.com" in host.lower() and not is_valid_brevo_smtp_key(password):
                raise ValidationError(
                    "Brevo SMTP key must start with xsmtpsib- from Brevo → SMTP & API."
                )
            config = EmailConfig(
                delivery="smtp",
                host=(cleaned.get("email_host") or "smtp-relay.brevo.com").strip(),
                port=int(cleaned.get("email_port") or 587),
                use_tls=bool(cleaned.get("email_use_tls") if cleaned.get("email_use_tls") is not None else True),
                use_ssl=bool(cleaned.get("email_use_ssl") if cleaned.get("email_use_ssl") is not None else False),
                username=host_user,
                password=password.replace(" ", ""),
                brevo_api_key=self._merged_secret("brevo_api_key"),
                resend_api_key=self._merged_secret("resend_api_key"),
                from_email=(cleaned.get("default_from_email") or "").strip(),
                from_name=(cleaned.get("email_from_name") or "SajiloWork").strip(),
                brand_logo_url=(cleaned.get("email_brand_logo_url") or "").strip(),
                brand_primary_color=(cleaned.get("email_brand_primary_color") or "#6366f1").strip(),
                footer_text=(cleaned.get("email_footer_text") or "").strip(),
                social_links=(cleaned.get("email_social_links") or "").strip(),
                smtp_timeout=15,
            )
            ok, message = test_smtp_configuration(config)
            if not ok and not is_valid_brevo_api_key(self._merged_secret("brevo_api_key")):
                raise ValidationError(
                    f"SMTP validation failed: {message}. "
                    "Add a Brevo API key for HTTPS fallback on hosts that block SMTP ports."
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
