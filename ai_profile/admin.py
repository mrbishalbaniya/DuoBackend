from django.contrib import admin

from .models import GeneratedProfileContent, SentenceTemplate


@admin.register(SentenceTemplate)
class SentenceTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "category",
        "subcategory",
        "style",
        "language",
        "weight",
        "active",
        "short_text",
        "updated_at",
    )
    list_filter = ("category", "style", "language", "active")
    search_fields = ("text", "subcategory", "category")
    list_editable = ("weight", "active")
    ordering = ("category", "subcategory", "-weight")

    @admin.display(description="Text")
    def short_text(self, obj: SentenceTemplate) -> str:
        return obj.text if len(obj.text) <= 72 else f"{obj.text[:69]}..."


@admin.register(GeneratedProfileContent)
class GeneratedProfileContentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "style",
        "language",
        "generation_version",
        "generated_at",
        "updated_at",
    )
    list_filter = ("style", "language", "generation_version")
    search_fields = ("user__username", "user__email", "generated_bio")
    readonly_fields = ("source_fingerprint", "generated_at", "created_at", "updated_at")
