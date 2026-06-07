from django.contrib import admin
from .models import Profile

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'age', 'location', 'religion', 'is_verified', 'is_onboarded']
    list_filter = ['religion', 'gender', 'is_verified', 'is_onboarded']
