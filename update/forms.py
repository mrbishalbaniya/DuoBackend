import logging

from django import forms

from update.models import AppVersion
from update.services.version import parse_release_notes

logger = logging.getLogger("update")


class AppVersionAdminForm(forms.ModelForm):
    release_notes_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "One release note per line"}),
        label="Release notes",
        help_text="Enter one bullet per line. Stored as JSON in the database.",
    )

    class Meta:
        model = AppVersion
        exclude = ["release_notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        notes = []
        if self.instance and self.instance.pk:
            raw = self.instance.release_notes
            if isinstance(raw, list):
                notes = [str(item).strip() for item in raw if str(item).strip()]
            elif isinstance(raw, str) and raw.strip():
                notes = parse_release_notes(raw)
        self.fields["release_notes_text"].initial = "\n".join(notes)

    def clean_release_notes_text(self):
        text = self.cleaned_data.get("release_notes_text") or ""
        return parse_release_notes(text)

    def clean(self):
        cleaned = super().clean()
        cleaned["release_notes"] = cleaned.get("release_notes_text") or []
        return cleaned

    def save(self, commit=True):
        notes = self.cleaned_data.get("release_notes_text") or []
        self.instance.release_notes = notes
        return super().save(commit=commit)
