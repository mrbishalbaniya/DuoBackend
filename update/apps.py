from django.apps import AppConfig


class UpdateConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "update"
    verbose_name = "App Updates"

    def ready(self):
        from update.signals import connect_signals

        connect_signals()
