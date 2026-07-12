from django.contrib import admin, messages
from django.utils.html import format_html

from update.models import AppVersion
from update.services.version import activate_version, publish_version, rollback_version


@admin.register(AppVersion)
class AppVersionAdmin(admin.ModelAdmin):
    list_display = (
        "version",
        "build_number",
        "platform",
        "channel",
        "status_badges",
        "file_size_label",
        "download_count",
        "published_at",
    )
    list_filter = ("platform", "channel", "is_active", "is_published", "force_update", "emergency_update")
    search_fields = ("version", "build_number", "apk_url", "checksum_sha256")
    readonly_fields = (
        "download_count",
        "file_size_label",
        "checksum_sha256",
        "file_size_bytes",
        "published_at",
        "created_at",
        "updated_at",
        "apk_preview",
    )
    fieldsets = (
        (
            "Release",
            {
                "fields": (
                    "version",
                    "build_number",
                    "platform",
                    "channel",
                    "release_notes",
                    "minimum_version",
                )
            },
        ),
        (
            "Distribution",
            {
                "fields": (
                    "apk_file",
                    "apk_url",
                    "apk_preview",
                    "file_size_bytes",
                    "file_size_label",
                    "checksum_sha256",
                    "download_count",
                )
            },
        ),
        (
            "Policy",
            {
                "fields": (
                    "soft_update",
                    "force_update",
                    "emergency_update",
                    "is_published",
                    "is_active",
                    "published_at",
                )
            },
        ),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )
    actions = ("publish_selected", "activate_selected", "rollback_selected", "deactivate_selected")

    @admin.display(description="Status")
    def status_badges(self, obj: AppVersion) -> str:
        badges = []
        if obj.is_active:
            badges.append('<span style="color:#16a34a;font-weight:700;">ACTIVE</span>')
        if obj.is_published:
            badges.append('<span style="color:#2563eb;">Published</span>')
        if obj.force_update:
            badges.append('<span style="color:#dc2626;">Force</span>')
        if obj.emergency_update:
            badges.append('<span style="color:#b91c1c;">Emergency</span>')
        return format_html(" · ".join(badges)) if badges else "—"

    @admin.display(description="APK")
    def apk_preview(self, obj: AppVersion) -> str:
        url = (obj.apk_url or "").strip()
        if not url and obj.apk_file:
            url = obj.apk_file.url
        if not url:
            return "—"
        return format_html('<a href="{}" target="_blank" rel="noopener">Download APK</a>', url)

    @admin.action(description="Publish selected releases")
    def publish_selected(self, request, queryset):
        count = 0
        for version in queryset:
            publish_version(version, activate=False)
            count += 1
        self.message_user(request, f"Published {count} release(s).", messages.SUCCESS)

    @admin.action(description="Activate selected release (per platform/channel)")
    def activate_selected(self, request, queryset):
        count = 0
        for version in queryset:
            activate_version(version)
            count += 1
        self.message_user(request, f"Activated {count} release(s).", messages.SUCCESS)

    @admin.action(description="Deactivate selected releases")
    def deactivate_selected(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {updated} release(s).", messages.WARNING)

    @admin.action(description="Rollback to previous published build")
    def rollback_selected(self, request, queryset):
        rolled = 0
        seen: set[tuple[str, str]] = set()
        for version in queryset:
            key = (version.platform, version.channel)
            if key in seen:
                continue
            seen.add(key)
            previous = rollback_version(platform=version.platform, channel=version.channel)
            if previous is not None:
                rolled += 1
        if rolled:
            self.message_user(request, f"Rolled back {rolled} channel(s).", messages.SUCCESS)
        else:
            self.message_user(request, "No previous release found to roll back to.", messages.ERROR)
