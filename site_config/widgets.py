from django import forms
from django.forms.utils import flatatt
from django.utils.html import format_html


class RevealablePasswordInput(forms.PasswordInput):
    """Password field with inline show/hide toggle (no external template dependency)."""

    def __init__(self, *args, configured: bool = False, **kwargs):
        self.configured = configured
        kwargs.setdefault("render_value", False)
        super().__init__(*args, **kwargs)
        if configured:
            self.attrs.setdefault(
                "placeholder",
                "Saved — leave blank to keep, or type a new value",
            )

    def render(self, name, value, attrs=None, renderer=None):
        final_attrs = self.build_attrs(
            attrs,
            {
                "type": "password",
                "name": name,
                "autocomplete": "new-password",
            },
        )
        input_id = final_attrs.get("id", f"id_{name}")
        final_attrs["id"] = input_id

        status = ""
        if self.configured:
            status = format_html(
                '<p class="duo-secret-status duo-secret-status--saved">'
                '<i class="fas fa-check-circle" aria-hidden="true"></i> '
                "A value is saved. Leave blank to keep it unchanged."
                "</p>"
            )

        return format_html(
            '<div class="duo-secret-field" data-duo-secret-field>'
            "{}"
            '<div class="duo-secret-input-row">'
            "<input{} />"
            '<button type="button" class="btn btn-sm btn-outline-secondary duo-secret-toggle" '
            'data-target="{}" aria-label="Show value">'
            '<i class="fas fa-eye" aria-hidden="true"></i> '
            "<span>Show</span>"
            "</button>"
            "</div>"
            "</div>",
            status,
            flatatt(final_attrs),
            input_id,
        )
