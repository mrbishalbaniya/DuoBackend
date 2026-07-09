from django.contrib import admin

from .models import AvatarConfig, AvatarOutfit


@admin.register(AvatarConfig)
class AvatarConfigAdmin(admin.ModelAdmin):
    list_display = ("user", "version", "updated_at")
    search_fields = ("user__username", "user__email")


@admin.register(AvatarOutfit)
class AvatarOutfitAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "is_favorite", "updated_at")
    search_fields = ("name", "user__username")
