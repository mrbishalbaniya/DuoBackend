from django import template
from django.urls import reverse

from admin_portal.menu import PORTAL_MENU_GROUPS, QUICK_ACTIONS
from admin_portal.services.activity import get_menu_badges

register = template.Library()


@register.simple_tag
def get_portal_menu():
    """Build grouped sidebar menu with admin URLs."""
    from django.contrib import admin

    badges = get_menu_badges()
    groups = []

    for group_def in PORTAL_MENU_GROUPS:
        items = []
        if "items" in group_def:
            for item in group_def["items"]:
                url = item.get("url")
                if item.get("url_name"):
                    try:
                        url = reverse(item["url_name"])
                    except Exception:
                        url = "#"
                items.append({**item, "url": url, "badge": 0})

        for app_label in group_def.get("apps", []):
            try:
                app_config = admin.site._registry
                models_in_app = [
                    (model, model_admin)
                    for model, model_admin in app_config.items()
                    if model._meta.app_label == app_label
                ]
            except Exception:
                models_in_app = []

            for model, model_admin in sorted(models_in_app, key=lambda x: x[0]._meta.verbose_name_plural):
                try:
                    url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")
                except Exception:
                    continue
                items.append({
                    "label": model._meta.verbose_name_plural.title(),
                    "url": url,
                    "icon": _icon_for_model(app_label, model._meta.model_name),
                    "badge": _badge_for_app(app_label, model._meta.model_name, badges),
                })

        if items:
            groups.append({
                "id": group_def["id"],
                "label": group_def["label"],
                "icon": group_def["icon"],
                "badge": sum(i.get("badge", 0) for i in items),
                "items": items,
            })
    return groups


def _icon_for_model(app_label, model_name):
    icons = {
        ("auth", "user"): "fas fa-user",
        ("accounts", "profile"): "fas fa-id-card",
        ("matching", "swipe"): "fas fa-hand-pointer",
        ("matching", "match"): "fas fa-fire",
        ("chat", "conversation"): "fas fa-comments",
        ("chat", "message"): "fas fa-envelope",
        ("subscriptions", "subscriptionpayment"): "fas fa-credit-card",
        ("subscriptions", "wallet"): "fas fa-wallet",
        ("security", "securityevent"): "fas fa-exclamation-triangle",
        ("analytics", "analyticsevent"): "fas fa-bolt",
        ("photo_verification", "userverification"): "fas fa-certificate",
        ("update", "appversion"): "fas fa-mobile-alt",
        ("site_config", "sitesettings"): "fas fa-cog",
    }
    return icons.get((app_label, model_name), "fas fa-circle")


def _badge_for_app(app_label, model_name, badges):
    if app_label == "photo_verification" and model_name == "userverification":
        return badges.get("verification", 0)
    if app_label == "subscriptions" and "payment" in model_name:
        return badges.get("payments", 0)
    if app_label == "chat" and model_name == "userreport":
        return badges.get("reports", 0)
    if app_label == "security":
        return badges.get("security", 0)
    return 0


@register.simple_tag
def get_quick_actions():
    return QUICK_ACTIONS


@register.simple_tag
def get_portal_badges():
    return get_menu_badges()
