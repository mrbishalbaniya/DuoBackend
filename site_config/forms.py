from django import forms

from site_config.models import SiteSettings

SECRET_FIELDS = (
    "google_client_secret",
    "email_host_password",
    "esewa_secret_key",
    "cloudinary_api_secret",
)


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in SECRET_FIELDS:
            field = self.fields.get(name)
            if not field:
                continue
            field.widget = forms.PasswordInput(render_value=False)
            field.required = False
            field.help_text = (
                field.help_text or "Leave blank when saving to keep the current value."
            )

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.pk:
            previous = SiteSettings.objects.filter(pk=instance.pk).first()
            if previous:
                for name in SECRET_FIELDS:
                    if not self.cleaned_data.get(name):
                        setattr(instance, name, getattr(previous, name))
        if commit:
            instance.save()
        return instance
