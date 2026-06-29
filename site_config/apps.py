from django.apps import AppConfig


class SiteConfigConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "site_config"
    verbose_name = "Site configuration"

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from site_config.models import SiteSettings

        def clear_cache(**kwargs):
            from duo_project.runtime_config import invalidate_integration_cache

            invalidate_integration_cache()

        post_save.connect(clear_cache, sender=SiteSettings)
        post_delete.connect(clear_cache, sender=SiteSettings)
