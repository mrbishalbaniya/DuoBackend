from pathlib import Path

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        env_file = Path(self.path).resolve().parent.parent / ".env"
        if env_file.exists():
            try:
                from django.utils import autoreload

                autoreload.watch_for_reload([str(env_file)])
            except Exception:
                pass
