from django.core.management.base import BaseCommand

from site_config.models import SiteSettings


class Command(BaseCommand):
    help = "Create the Integration settings row in admin (idempotent)."

    def handle(self, *args, **options):
        obj = SiteSettings.get_solo()
        self.stdout.write(
            self.style.SUCCESS(
                f"Integration settings ready (pk={obj.pk}). "
                "Edit them at /admin/site_config/sitesettings/1/change/"
            )
        )
