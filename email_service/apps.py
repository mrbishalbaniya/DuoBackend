from django.apps import AppConfig


class EmailServiceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "email_service"
    verbose_name = "Email service"

    def ready(self):
        from email_service import signals  # noqa: F401
        from email_service import triggers  # noqa: F401  (sends templated emails on events)
