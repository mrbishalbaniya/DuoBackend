from django.contrib import admin
from django.utils.html import format_html

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "username",
        "full_name",
        "user_email",
        "phone_display",
    ]
    list_display_links = ("full_name",)
    list_select_related = ("user",)
    list_filter = [
        "gender",
        "religion",
        "work_preference",
        "relationship_goal",
        "pref_gender",
        "pref_relationship_goal",
        "pref_verified_only",
        "is_verified",
        "is_onboarded",
        "created_at",
    ]
    search_fields = [
        "full_name",
        "user__username",
        "user__email",
        "phone_number",
        "location",
        "education",
        "occupation",
        "bio",
    ]
    readonly_fields = [
        "profile_completeness_display",
        "photo_preview_large",
        "gallery_preview",
        "lifestyle_tags_display",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]
    list_per_page = 25
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Account",
            {
                "fields": (
                    "user",
                    "full_name",
                    "phone_country_code",
                    "phone_number",
                    "is_verified",
                    "is_onboarded",
                    "profile_completeness_display",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
        (
            "Personal",
            {
                "fields": (
                    "age",
                    "gender",
                    "location",
                    "bio",
                    "religion",
                    "relationship_goal",
                ),
            },
        ),
        (
            "Education & work",
            {
                "fields": (
                    "education",
                    "occupation",
                    "work_preference",
                ),
            },
        ),
        (
            "Lifestyle",
            {
                "fields": (
                    "lifestyle_tags",
                    "lifestyle_tags_display",
                ),
            },
        ),
        (
            "Photos",
            {
                "fields": (
                    "photo_url",
                    "photo_preview_large",
                    "photo_urls",
                    "gallery_preview",
                ),
            },
        ),
        (
            "Partner preferences",
            {
                "fields": (
                    "pref_age_min",
                    "pref_age_max",
                    "pref_min_height",
                    "pref_occupation",
                    "pref_gender",
                    "pref_location",
                    "pref_max_distance_km",
                    "pref_relationship_goal",
                    "pref_verified_only",
                    "pref_values",
                ),
            },
        ),
    )

    @admin.display(description="Username", ordering="user__username")
    def username(self, obj):
        return obj.user.username or "—"

    @admin.display(description="Email", ordering="user__email")
    def user_email(self, obj):
        return obj.user.email or "—"

    @admin.display(description="Phone")
    def phone_display(self, obj):
        if not obj.phone_number:
            return "—"
        code = (obj.phone_country_code or "").strip()
        return f"{code} {obj.phone_number}".strip()

    @admin.display(description="Profile completeness")
    def profile_completeness_display(self, obj):
        return f"{obj.profile_completeness}%"

    @admin.display(description="Profile photo")
    def photo_preview_large(self, obj):
        if not obj.photo_url:
            return "—"
        return format_html(
            '<a href="{0}" target="_blank" rel="noopener noreferrer">'
            '<img src="{0}" style="max-height:180px;max-width:180px;object-fit:cover;border-radius:12px;" />'
            "</a>",
            obj.photo_url,
        )

    @admin.display(description="Gallery")
    def gallery_preview(self, obj):
        urls = obj.photo_urls if isinstance(obj.photo_urls, list) else []
        if not urls:
            return "—"
        items = []
        for url in urls[:6]:
            if not url:
                continue
            items.append(
                format_html(
                    '<a href="{0}" target="_blank" rel="noopener noreferrer" style="margin-right:8px;">'
                    '<img src="{0}" style="height:72px;width:72px;object-fit:cover;border-radius:10px;" />'
                    "</a>",
                    url,
                )
            )
        return format_html("".join(str(item) for item in items)) if items else "—"

    @admin.display(description="Lifestyle tags (readable)")
    def lifestyle_tags_display(self, obj):
        tags = obj.lifestyle_tags if isinstance(obj.lifestyle_tags, list) else []
        return ", ".join(str(tag) for tag in tags if tag) or "—"
