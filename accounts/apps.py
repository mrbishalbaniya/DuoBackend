from pathlib import Path

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        from duo_project.cache.signals import connect_cache_signals

        connect_cache_signals()

        from duo_project.realtime.signals import connect_realtime_signals

        connect_realtime_signals()

        from duo_project.media import signals as _media_signals  # noqa: F401
        import duo_project.celery_admin  # noqa: F401 — register TaskResult admin

        env_file = Path(self.path).resolve().parent.parent / ".env"
        if env_file.exists():
            try:
                from django.utils import autoreload

                autoreload.watch_for_reload([str(env_file)])
            except Exception:
                pass
