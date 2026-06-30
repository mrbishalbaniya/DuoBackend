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

            configured = bool(instance and instance.pk and getattr(instance, name, ""))
            field.widget = RevealablePasswordInput(configured=configured)
            field.required = False
            field.help_text = (
                "Leave blank when saving to keep the current value."
                if configured
                else "Enter the secret value."
            )

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.pk = instance.pk or SiteSettings.SINGLETON_PK

        previous = SiteSettings.objects.filter(pk=SiteSettings.SINGLETON_PK).first()
        if previous:
            for name in SECRET_FIELDS:
                new_value = self.cleaned_data.get(name)
                if not new_value:
                    setattr(instance, name, getattr(previous, name))

        if commit:
            instance.save()
            self.save_m2m()
        return instance
