from django.contrib import admin

from notifications.models import DeviceToken


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "platform", "is_active", "updated_at", "token_preview")
    list_filter = ("platform", "is_active")
    search_fields = ("user__username", "user__email", "token")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Token")
    def token_preview(self, obj):
        return f"{obj.token[:18]}…"
