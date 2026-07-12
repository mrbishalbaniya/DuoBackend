from django.core.management.base import BaseCommand

from analytics.permissions import ensure_analytics_groups
from analytics.services.aggregation.snapshots import aggregate_daily, aggregate_hourly


class Command(BaseCommand):
    help = "Aggregate analytics metrics into hourly and daily snapshots."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hourly",
            action="store_true",
            help="Run hourly aggregation only.",
        )
        parser.add_argument(
            "--daily",
            action="store_true",
            help="Run daily aggregation only.",
        )
        parser.add_argument(
            "--setup-groups",
            action="store_true",
            help="Create analytics RBAC groups.",
        )

    def handle(self, *args, **options):
        if options["setup_groups"]:
            ensure_analytics_groups()
            self.stdout.write(self.style.SUCCESS("Analytics RBAC groups ensured."))

        run_hourly = options["hourly"] or not options["daily"]
        run_daily = options["daily"] or not options["hourly"]

        if run_hourly:
            aggregate_hourly()
            self.stdout.write(self.style.SUCCESS("Hourly analytics snapshot updated."))

        if run_daily:
            aggregate_daily()
            self.stdout.write(self.style.SUCCESS("Daily analytics snapshot updated."))
