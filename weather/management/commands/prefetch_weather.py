from django.core.management.base import BaseCommand

from weather.services.openweather import OpenWeatherError, OpenWeatherService

# Kathmandu metro bbox — background warm cache for demo/sync
DEFAULT_BBOX = {
    "lat_min": 27.4,
    "lat_max": 28.0,
    "lon_min": 85.0,
    "lon_max": 85.6,
    "step": 4,
}


class Command(BaseCommand):
    help = "Prefetch OpenWeather grid snapshots into cache (background sync)."

    def add_arguments(self, parser):
        parser.add_argument("--lat-min", type=float, default=DEFAULT_BBOX["lat_min"])
        parser.add_argument("--lat-max", type=float, default=DEFAULT_BBOX["lat_max"])
        parser.add_argument("--lon-min", type=float, default=DEFAULT_BBOX["lon_min"])
        parser.add_argument("--lon-max", type=float, default=DEFAULT_BBOX["lon_max"])
        parser.add_argument("--step", type=int, default=DEFAULT_BBOX["step"])

    def handle(self, *args, **options):
        try:
            service = OpenWeatherService()
        except OpenWeatherError as exc:
            self.stderr.write(str(exc))
            return

        points = service.grid_snapshot(
            options["lat_min"],
            options["lat_max"],
            options["lon_min"],
            options["lon_max"],
            options["step"],
        )
        self.stdout.write(self.style.SUCCESS(f"Cached {len(points)} weather grid points."))
