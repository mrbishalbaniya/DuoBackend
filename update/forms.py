import logging

from django import forms

from update.models import AppVersion
from update.services.release_notes import parse_release_notes, resolve_release_title

logger = logging.getLogger("update")


class AppVersionAdminForm(forms.ModelForm):
    release_title = forms.CharField(
        required=False,
        max_length=120,
        label="Release Title",
        help_text="Short customer-facing headline, e.g. “Performance & Stability Update”.",
        widget=forms.TextInput(
            attrs={"placeholder": "Performance & Stability Update", "style": "width: 32em;"}
        ),
    )
    release_notes_text = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 8,
                "placeholder": (
                    "Improved matching recommendations.\n"
                    "Faster chat performance.\n"
                    "General stability improvements."
                ),
            }
        ),
        label="Release Notes",
        help_text=(
            "One business-friendly bullet per line. "
            "Do not paste GitHub release bodies, commit hashes, APK names, or install help."
        ),
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
            self.fields["release_title"].initial = self.instance.release_title or ""
        self.fields["release_notes_text"].initial = "\n".join(notes)

    def clean_release_title(self):
        title = (self.cleaned_data.get("release_title") or "").strip()
        if not title:
            return ""
        cleaned = resolve_release_title(title)
        # Reject auto-generated fallbacks when the typed title was invalid.
        if cleaned in {"App Update", "Performance & Stability Update"} and title.casefold() != cleaned.casefold():
            return ""
        return cleaned

    def clean_release_notes_text(self):
        text = self.cleaned_data.get("release_notes_text") or ""
        return parse_release_notes(text)

    def clean(self):
        cleaned = super().clean()
        cleaned["release_notes"] = cleaned.get("release_notes_text") or []
        return cleaned

    def save(self, commit=True):
        notes = self.cleaned_data.get("release_notes_text") or []
        title = self.cleaned_data.get("release_title") or ""
        self.instance.release_notes = notes
        self.instance.release_title = title
        return super().save(commit=commit)
