from django.core.management.base import BaseCommand

from update.services.bootstrap import initialize_update_service


class Command(BaseCommand):
    help = "Ensure update app migrations are applied and seed baseline AppVersion rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-migrate",
            action="store_true",
            help="Only seed/check — do not run migrate update.",
        )

    def handle(self, *args, **options):
        result = initialize_update_service(apply_migrations=not options["skip_migrate"])

        if not result["database_ready"]:
            self.stderr.write(
                self.style.ERROR(
                    "Update service database is NOT ready. "
                    "The update_appversion table is missing. "
                    "Run: python manage.py migrate update"
                )
            )
            raise SystemExit(1)

        if result["seeded"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Seeded {result['seeded']} baseline AppVersion record(s)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Update service ready ({result['version_count']} version record(s))."
                )
            )
