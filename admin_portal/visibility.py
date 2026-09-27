"""Hide low-value admin models everywhere the portal lists them.

The hide list lives in JAZZMIN_SETTINGS["hide_models"] ("app_label.ModelName").
Jazzmin applies it to its own menus only, so the portal sidebar and Django's
app index pages (for example /admin/analytics/) check it through here.
Hidden models stay registered, so their pages still open by direct URL.
"""

from __future__ import annotations

from django.conf import settings


def hidden_model_keys() -> set[str]:
    hide = getattr(settings, "JAZZMIN_SETTINGS", {}).get("hide_models", [])
    return {str(name).lower() for name in hide}


def is_model_hidden(model) -> bool:
    key = f"{model._meta.app_label}.{model._meta.model_name}"
    return key in hidden_model_keys()


def install_app_list_filter(site) -> None:
    """Drop hidden models from AdminSite.get_app_list (index and app pages)."""
    original_get_app_list = site.get_app_list

    def get_app_list(request, app_label=None):
        hidden = hidden_model_keys()
        full_list = original_get_app_list(request, app_label)
        apps = []
        for app in full_list:
            models = [
                model
                for model in app["models"]
                if f"{app['app_label']}.{model['object_name']}".lower() not in hidden
            ]
            if models:
                apps.append({**app, "models": models})
        # An app page with every model hidden would 404 (breadcrumbs link
        # there), so show its full list instead.
        if app_label and not apps:
            return full_list
        return apps

    site.get_app_list = get_app_list
