from django.apps import AppConfig


class AdminPortalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "admin_portal"
    verbose_name = "Admin Portal"

    def ready(self):
        from django.contrib import admin

        from admin_portal.visibility import install_app_list_filter

        install_app_list_filter(admin.site)
