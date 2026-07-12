"""Role-based access control for the analytics platform."""

from rest_framework.permissions import BasePermission

from analytics.constants import ANALYTICS_GROUPS

FINANCE_MODULES = {"revenue", "forecast", "exports"}
SUPPORT_MODULES = {"security", "fraud", "users", "chat"}
MARKETING_MODULES = {"users", "funnel", "retention", "cohort", "behavior", "maps", "matching"}
READ_ONLY_MODULES = {"dashboard", "reports"}

MODULE_PERMISSIONS = {
    "dashboard": {"analytics_super_admin", "analytics_admin", "analytics_analyst", "analytics_finance", "analytics_support", "analytics_marketing"},
    "revenue": {"analytics_super_admin", "analytics_admin", "analytics_finance", "analytics_analyst"},
    "users": {"analytics_super_admin", "analytics_admin", "analytics_analyst", "analytics_marketing", "analytics_support"},
    "matching": {"analytics_super_admin", "analytics_admin", "analytics_analyst", "analytics_marketing"},
    "chat": {"analytics_super_admin", "analytics_admin", "analytics_analyst", "analytics_support"},
    "maps": {"analytics_super_admin", "analytics_admin", "analytics_analyst", "analytics_marketing"},
    "funnel": {"analytics_super_admin", "analytics_admin", "analytics_analyst", "analytics_marketing"},
    "retention": {"analytics_super_admin", "analytics_admin", "analytics_analyst", "analytics_marketing"},
    "cohort": {"analytics_super_admin", "analytics_admin", "analytics_analyst", "analytics_marketing"},
    "behavior": {"analytics_super_admin", "analytics_admin", "analytics_analyst", "analytics_marketing"},
    "forecast": {"analytics_super_admin", "analytics_admin", "analytics_finance", "analytics_analyst"},
    "fraud": {"analytics_super_admin", "analytics_admin", "analytics_support"},
    "security": {"analytics_super_admin", "analytics_admin", "analytics_support"},
    "system": {"analytics_super_admin", "analytics_admin"},
    "reports": {"analytics_super_admin", "analytics_admin", "analytics_analyst", "analytics_finance", "analytics_marketing"},
    "exports": {"analytics_super_admin", "analytics_admin", "analytics_finance", "analytics_analyst"},
}


def user_analytics_groups(user) -> set[str]:
    if not user or not user.is_authenticated:
        return set()
    if user.is_superuser:
        return set(ANALYTICS_GROUPS.keys())
    return set(user.groups.filter(name__in=ANALYTICS_GROUPS).values_list("name", flat=True))


def user_can_access_module(user, module: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    allowed = MODULE_PERMISSIONS.get(module, set())
    return bool(user_analytics_groups(user) & allowed)


class IsAnalyticsUser(BasePermission):
    """Staff or member of any analytics group."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.is_staff:
            return True
        return bool(user_analytics_groups(user))


class AnalyticsModulePermission(BasePermission):
    """Permission class parameterized by analytics module."""

    module = "dashboard"

    def has_permission(self, request, view):
        module = getattr(view, "analytics_module", self.module)
        return user_can_access_module(request.user, module)


def ensure_analytics_groups():
    """Create analytics RBAC groups (idempotent)."""
    from django.contrib.auth.models import Group

    for name, label in ANALYTICS_GROUPS.items():
        Group.objects.get_or_create(name=name)
