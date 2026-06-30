from django import forms

from site_config.models import SiteSettings
from site_config.widgets import RevealablePasswordInput

SECRET_FIELDS = (
    "google_client_secret",
    "email_host_password",
    "esewa_secret_key",
    "cloudinary_api_secret",
)


class SiteSettingsForm(forms.ModelForm):
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
                "A value is already saved (hidden). Leave blank to keep it, or type a new value to replace it."
                if configured
                else "Enter the secret value, then click Save at the bottom of the page."
            )

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.pk = SiteSettings.SINGLETON_PK

        previous = SiteSettings.objects.filter(pk=SiteSettings.SINGLETON_PK).first()
        if previous:
            for name in SECRET_FIELDS:
                new_value = (self.cleaned_data.get(name) or "").strip()
                if not new_value:
                    setattr(instance, name, getattr(previous, name))

        if commit:
            instance.save()
            self.save_m2m()
        return instance
