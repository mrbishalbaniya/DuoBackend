"""Create or update the Django admin superuser from environment variables."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from decouple import config


class Command(BaseCommand):
    help = (
        "Ensure a superuser exists using DJANGO_SUPERUSER_USERNAME, "
        "DJANGO_SUPERUSER_EMAIL, and DJANGO_SUPERUSER_PASSWORD."
    )

    def handle(self, *args, **options):
        username = config("DJANGO_SUPERUSER_USERNAME", default="").strip()
        email = config("DJANGO_SUPERUSER_EMAIL", default="").strip()
        password = config("DJANGO_SUPERUSER_PASSWORD", default="")

        if not username or not password:
            self.stdout.write(
                self.style.WARNING(
                    "Skipping superuser setup — set DJANGO_SUPERUSER_USERNAME and "
                    "DJANGO_SUPERUSER_PASSWORD to create or reset admin access."
                )
            )
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email or f"{username}@example.com"},
        )

        user.email = email or user.email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created superuser: {username}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Updated superuser password: {username}"))
