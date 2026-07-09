from __future__ import annotations

import hashlib
import logging
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

OPENWEATHER_BASE = "https://api.openweathermap.org"
GEOCODE_BASE = "https://api.openweathermap.org/geo/1.0"
TILE_BASE = "https://tile.openweathermap.org/map"

CACHE_TTL = {
    "current": 600,
    "forecast": 1800,
    "onecall": 600,
    "air": 1800,
    "geocode": 86_400,
    "reverse": 86_400,
    "tile": 600,
    "grid": 900,
    "summary": 480,
}

VALID_TILE_LAYERS = frozenset(
    {
        "temp_new",
        "clouds_new",
        "precipitation_new",
        "pressure_new",
        "wind_new",
    }
)


class OpenWeatherError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class OpenWeatherService:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or getattr(settings, "OPENWEATHER_API_KEY", "")
        if not self.api_key:
            raise OpenWeatherError("OpenWeather API key is not configured.", status_code=503)

    def _cache_key(self, namespace: str, *parts: Any) -> str:
        raw = ":".join(str(p) for p in parts)
        digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return f"weather:{namespace}:{digest}"

    def _get_json(self, url: str, params: dict[str, Any], cache_key: str, ttl: int) -> dict[str, Any]:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        params = {**params, "appid": self.api_key}
        try:
            response = requests.get(url, params=params, timeout=12)
        except requests.RequestException as exc:
            logger.warning("OpenWeather request failed: %s", exc)
            raise OpenWeatherError("Weather service unavailable.", status_code=503) from exc

        if response.status_code == 401:
            raise OpenWeatherError("Invalid OpenWeather API key.", status_code=503)
        if response.status_code == 429:
            raise OpenWeatherError("Weather API rate limit exceeded. Try again shortly.", status_code=429)
        if not response.ok:
            logger.warning("OpenWeather %s returned %s", url, response.status_code)
            raise OpenWeatherError("Weather upstream error.", status_code=502)

        data = response.json()
        cache.set(cache_key, data, ttl)
        return data

    def current(self, lat: float, lon: float) -> dict[str, Any]:
        key = self._cache_key("current", round(lat, 3), round(lon, 3))
        return self._get_json(
            f"{OPENWEATHER_BASE}/data/2.5/weather",
            {"lat": lat, "lon": lon, "units": "metric"},
            key,
            CACHE_TTL["current"],
        )

    def forecast(self, lat: float, lon: float) -> dict[str, Any]:
        key = self._cache_key("forecast", round(lat, 3), round(lon, 3))
        return self._get_json(
            f"{OPENWEATHER_BASE}/data/2.5/forecast",
            {"lat": lat, "lon": lon, "units": "metric"},
            key,
            CACHE_TTL["forecast"],
        )

    def onecall(self, lat: float, lon: float) -> dict[str, Any]:
        key = self._cache_key("onecall", round(lat, 3), round(lon, 3))
        try:
            return self._get_json(
                f"{OPENWEATHER_BASE}/data/3.0/onecall",
                {"lat": lat, "lon": lon, "units": "metric", "exclude": "minutely"},
                key,
                CACHE_TTL["onecall"],
            )
        except OpenWeatherError:
            return self._build_onecall_fallback(lat, lon)

    def _build_onecall_fallback(self, lat: float, lon: float) -> dict[str, Any]:
        current = self.current(lat, lon)
        forecast = self.forecast(lat, lon)
        return {
            "lat": lat,
            "lon": lon,
            "timezone": forecast.get("city", {}).get("timezone", 0),
            "current": self._normalize_current(current),
            "hourly": self._normalize_hourly(forecast),
            "daily": self._normalize_daily(forecast),
            "alerts": [],
            "_source": "fallback",
        }

    def air_pollution(self, lat: float, lon: float) -> dict[str, Any]:
        key = self._cache_key("air", round(lat, 3), round(lon, 3))
        return self._get_json(
            f"{OPENWEATHER_BASE}/data/2.5/air_pollution",
            {"lat": lat, "lon": lon},
            key,
            CACHE_TTL["air"],
        )

    def geocode(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        key = self._cache_key("geocode", query.lower(), limit)
        cached = cache.get(key)
        if cached is not None:
            return cached
        params = {"q": query, "limit": limit, "appid": self.api_key}
        try:
            response = requests.get(f"{GEOCODE_BASE}/direct", params=params, timeout=12)
        except requests.RequestException as exc:
            raise OpenWeatherError("Geocoding unavailable.", status_code=503) from exc
        if not response.ok:
            raise OpenWeatherError("Geocoding upstream error.", status_code=502)
        data = response.json()
        cache.set(key, data, CACHE_TTL["geocode"])
        return data

    def reverse_geocode(self, lat: float, lon: float, limit: int = 1) -> list[dict[str, Any]]:
        key = self._cache_key("reverse", round(lat, 3), round(lon, 3), limit)
        cached = cache.get(key)
        if cached is not None:
            return cached
        params = {"lat": lat, "lon": lon, "limit": limit, "appid": self.api_key}
        try:
            response = requests.get(f"{GEOCODE_BASE}/reverse", params=params, timeout=12)
        except requests.RequestException as exc:
            raise OpenWeatherError("Reverse geocoding unavailable.", status_code=503) from exc
        if not response.ok:
            raise OpenWeatherError("Reverse geocoding upstream error.", status_code=502)
        data = response.json()
        cache.set(key, data, CACHE_TTL["reverse"])
        return data

    def tile_png(self, layer: str, z: int, x: int, y: int) -> bytes:
        if layer not in VALID_TILE_LAYERS:
            raise OpenWeatherError("Unsupported weather tile layer.", status_code=400)
        key = self._cache_key("tile", layer, z, x, y)
        cached = cache.get(key)
        if cached is not None:
            return cached
        url = f"{TILE_BASE}/{layer}/{z}/{x}/{y}.png"
        try:
            response = requests.get(url, params={"appid": self.api_key}, timeout=12)
        except requests.RequestException as exc:
            raise OpenWeatherError("Weather tile unavailable.", status_code=503) from exc
        if response.status_code == 429:
            raise OpenWeatherError("Weather tile rate limit exceeded.", status_code=429)
        if not response.ok:
            raise OpenWeatherError("Weather tile upstream error.", status_code=502)
        content = response.content
        cache.set(key, content, CACHE_TTL["tile"])
        return content

    def grid_snapshot(self, lat_min: float, lat_max: float, lon_min: float, lon_max: float, step: int = 3) -> list[dict[str, Any]]:
        step = max(2, min(step, 6))
        key = self._cache_key("grid", lat_min, lat_max, lon_min, lon_max, step)
        cached = cache.get(key)
        if cached is not None:
            return cached

        points: list[dict[str, Any]] = []
        lat = lat_min
        while lat <= lat_max:
            lon = lon_min
            while lon <= lon_max:
                try:
                    current = self.current(lat, lon)
                    points.append(self._normalize_current(current) | {"lat": lat, "lon": lon})
                except OpenWeatherError:
                    pass
                lon += step
            lat += step

        cache.set(key, points, CACHE_TTL["grid"])
        return points

    def summary(self, lat: float, lon: float) -> dict[str, Any]:
        key = self._cache_key("summary", round(lat, 3), round(lon, 3))
        cached = cache.get(key)
        if cached is not None:
            return cached

        onecall = self.onecall(lat, lon)
        air = None
        try:
            air = self.air_pollution(lat, lon)
        except OpenWeatherError:
            air = None

        places = []
        try:
            places = self.reverse_geocode(lat, lon, limit=1)
        except OpenWeatherError:
            places = []

        payload = {
            "lat": lat,
            "lon": lon,
            "place": places[0] if places else None,
            "onecall": onecall,
            "air_pollution": air,
        }
        cache.set(key, payload, CACHE_TTL["summary"])
        return payload

    @staticmethod
    def _normalize_current(data: dict[str, Any]) -> dict[str, Any]:
        main = data.get("main", {})
        wind = data.get("wind", {})
        weather = (data.get("weather") or [{}])[0]
        sys = data.get("sys", {})
        return {
            "dt": data.get("dt"),
            "temp": main.get("temp"),
            "feels_like": main.get("feels_like"),
            "pressure": main.get("pressure"),
            "humidity": main.get("humidity"),
            "visibility": data.get("visibility"),
            "uvi": data.get("uvi"),
            "clouds": (data.get("clouds") or {}).get("all"),
            "wind_speed": wind.get("speed"),
            "wind_deg": wind.get("deg"),
            "condition": weather.get("main"),
            "description": weather.get("description"),
            "icon": weather.get("icon"),
            "sunrise": sys.get("sunrise"),
            "sunset": sys.get("sunset"),
        }

    @staticmethod
    def _normalize_hourly(forecast: dict[str, Any]) -> list[dict[str, Any]]:
        items = []
        for entry in forecast.get("list", [])[:16]:
            main = entry.get("main", {})
            weather = (entry.get("weather") or [{}])[0]
            items.append(
                {
                    "dt": entry.get("dt"),
                    "temp": main.get("temp"),
                    "pop": entry.get("pop"),
                    "humidity": main.get("humidity"),
                    "wind_speed": entry.get("wind", {}).get("speed"),
                    "condition": weather.get("main"),
                    "icon": weather.get("icon"),
                }
            )
        return items

    @staticmethod
    def _normalize_daily(forecast: dict[str, Any]) -> list[dict[str, Any]]:
        by_day: dict[str, dict[str, Any]] = {}
        for entry in forecast.get("list", []):
            day = entry.get("dt_txt", "")[:10]
            if not day:
                continue
            main = entry.get("main", {})
            weather = (entry.get("weather") or [{}])[0]
            slot = by_day.setdefault(
                day,
                {
                    "date": day,
                    "temp_min": main.get("temp_min"),
                    "temp_max": main.get("temp_max"),
                    "pop": entry.get("pop", 0),
                    "condition": weather.get("main"),
                    "icon": weather.get("icon"),
                },
            )
            slot["temp_min"] = min(slot.get("temp_min", main.get("temp_min")), main.get("temp_min"))
            slot["temp_max"] = max(slot.get("temp_max", main.get("temp_max")), main.get("temp_max"))
            slot["pop"] = max(slot.get("pop", 0), entry.get("pop", 0))
        return list(by_day.values())[:7]
