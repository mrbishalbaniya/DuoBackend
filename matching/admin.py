from django.contrib import admin
from .models import Swipe, Match

@admin.register(Swipe)
class SwipeAdmin(admin.ModelAdmin):
    list_display = ['from_user', 'to_user', 'action', 'created_at']

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ['user1', 'user2', 'compatibility_score', 'matched_at']
