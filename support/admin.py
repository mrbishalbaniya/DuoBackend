from django.contrib import admin

from .models import SupportRequest


@admin.register(SupportRequest)
class SupportRequestAdmin(admin.ModelAdmin):
    list_display = ["id", "category", "subject", "user", "status", "created_at"]
    list_filter = ["category", "status", "created_at"]
    search_fields = ["subject", "message", "contact_email", "user__username", "user__email"]
    readonly_fields = ["user", "category", "subject", "message", "contact_email", "device_info", "created_at", "updated_at"]
    list_editable = ["status"]
