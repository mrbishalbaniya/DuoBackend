from django.contrib import admin, messages

from notifications.models import DeviceToken, NotificationPreference, PushDeliveryLog


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "platform",
        "device_label",
        "is_active",
        "last_used_at",
        "updated_at",
        "token_preview",
    )
    list_filter = ("platform", "is_active")
    search_fields = ("user__username", "user__email", "token", "device_label")
    readonly_fields = ("created_at", "updated_at", "last_used_at")

    @admin.display(description="Token")
    def token_preview(self, obj):
        return f"{obj.token[:18]}…"


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "push_enabled",
        "chat_enabled",
        "match_enabled",
        "likes_enabled",
        "updated_at",
    )
    list_filter = ("push_enabled", "chat_enabled", "match_enabled", "likes_enabled")
    search_fields = ("user__username", "user__email")


@admin.register(PushDeliveryLog)
class PushDeliveryLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "user",
        "notification_type",
        "status",
        "devices_sent",
        "devices_targeted",
        "skip_reason",
    )
    list_filter = ("status", "notification_type", "created_at")
    search_fields = ("user__username", "title", "body", "skip_reason")
    readonly_fields = (
        "user",
        "notification_type",
        "title",
        "body",
        "status",
        "devices_targeted",
        "devices_sent",
        "skip_reason",
        "error_message",
        "payload",
        "created_at",
    )

    def has_add_permission(self, request):
        return False


@admin.action(description="Retry failed push (re-send to selected users)")
def retry_failed_push(modeladmin, request, queryset):
    count = 0
    for log in queryset.filter(status=PushDeliveryLog.STATUS_FAILED):
        from notifications.services.notification_service import send_push_notification

        send_push_notification(
            user_id=log.user_id,
            notification_type=log.notification_type,
            title=log.title,
            body=log.body,
            data={k: str(v) for k, v in (log.payload or {}).items()},
            deduplicate=False,
        )
        count += 1
    messages.success(request, f"Retried {count} failed notification(s).")


PushDeliveryLogAdmin.actions = [retry_failed_push]
