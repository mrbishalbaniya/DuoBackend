from django.apps import AppConfig


class PhotoVerificationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "photo_verification"
    verbose_name = "Photo verification"

    def ready(self):
        from photo_verification import signals  # noqa: F401  (registers receivers)
