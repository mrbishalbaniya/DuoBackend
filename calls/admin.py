from django.contrib import admin

from calls.models import CallSession


@admin.register(CallSession)
class CallSessionAdmin(admin.ModelAdmin):
    list_display = (
        "public_id",
        "call_type",
        "status",
        "caller",
        "callee",
        "duration_seconds",
        "started_at",
    )
    list_filter = ("status", "call_type")
    search_fields = ("public_id", "caller__username", "callee__username")
    readonly_fields = ("public_id", "started_at", "answered_at", "ended_at", "duration_seconds")
