from django import forms
from django.forms.utils import flatatt
from django.utils.html import format_html


class RevealablePasswordInput(forms.PasswordInput):
    """Password field with show/hide toggle and a configured-state hint."""

    template_name = "site_config/widgets/revealable_password.html"

    def __init__(self, *args, configured: bool = False, **kwargs):
        self.configured = configured
        kwargs.setdefault("render_value", False)
        super().__init__(*args, **kwargs)
        if configured:
            self.attrs.setdefault(
                "placeholder",
                "Saved — leave blank to keep, or type a new value",
            )

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["configured"] = self.configured
        return context

    def render(self, name, value, attrs=None, renderer=None):
        # Fallback if template loading fails in tests.
        if renderer is None:
            renderer = self.renderer
        try:
            return super().render(name, value, attrs, renderer)
        except Exception:
            final_attrs = self.build_attrs(attrs, {"type": self.input_type, "name": name})
            input_id = final_attrs.get("id", name)
            return format_html(
                '<div class="duo-secret-field"><input{} />'
                '<button type="button" class="duo-secret-toggle" data-target="{}">Show</button></div>',
                flatatt(final_attrs),
                input_id,
            )

    class Media:
        js = ("site_config/js/revealable_password.js",)
