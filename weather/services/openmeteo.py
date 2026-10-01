"""Keyless weather service backed by Open-Meteo (https://open-meteo.com).

Open-Meteo is free and needs no API key. Responses are reshaped into the
OpenWeather formats the frontend already understands, so the map, widgets and
popups work unchanged. Reverse geocoding uses OpenStreetMap Nominatim, which is
also free and keyless (its usage policy asks for a User-Agent and light,
cached use).
"""
from __future__ import annotations

import base64
import hashlib
import logging
import time
from datetime import datetime
from typing import Any

import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "DuoDatingApp/1.0 (weather; contact: admin@duo.local)"

CACHE_TTL = {
    "current": 600,
    "forecast": 1800,
    "onecall": 600,
    "air": 1800,
    "geocode": 86_400,
    "reverse": 86_400,
    "grid": 900,
    "summary": 480,
}

# 1x1 transparent PNG, returned for the retired raster weather tiles.
_TRANSPARENT_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)

# WMO weather code -> (OpenWeather id, main, description, icon base)
_WMO = {
    0: (800, "Clear", "clear sky", "01"),
    1: (801, "Clouds", "mainly clear", "02"),
    2: (802, "Clouds", "partly cloudy", "03"),
    3: (804, "Clouds", "overcast clouds", "04"),
    45: (741, "Fog", "fog", "50"),
    48: (741, "Fog", "depositing rime fog", "50"),
    51: (300, "Drizzle", "light drizzle", "09"),
    53: (301, "Drizzle", "drizzle", "09"),
    55: (302, "Drizzle", "dense drizzle", "09"),
    56: (311, "Drizzle", "light freezing drizzle", "09"),
    57: (312, "Drizzle", "dense freezing drizzle", "09"),
    61: (500, "Rain", "light rain", "10"),
    63: (501, "Rain", "moderate rain", "10"),
    65: (502, "Rain", "heavy rain", "10"),
    66: (511, "Rain", "light freezing rain", "13"),
    67: (511, "Rain", "heavy freezing rain", "13"),
    71: (600, "Snow", "light snow", "13"),
    73: (601, "Snow", "snow", "13"),
    75: (602, "Snow", "heavy snow", "13"),
    77: (600, "Snow", "snow grains", "13"),
    80: (520, "Rain", "light rain showers", "09"),
    81: (521, "Rain", "rain showers", "09"),
    82: (522, "Rain", "violent rain showers", "09"),
    85: (620, "Snow", "light snow showers", "13"),
    86: (621, "Snow", "heavy snow showers", "13"),
    95: (211, "Thunderstorm", "thunderstorm", "11"),
    96: (201, "Thunderstorm", "thunderstorm with light hail", "11"),
    99: (202, "Thunderstorm", "thunderstorm with heavy hail", "11"),
}

_CURRENT_VARS = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,rain,"
    "showers,snowfall,weather_code,cloud_cover,pressure_msl,wind_speed_10m,"
    "wind_direction_10m,visibility,uv_index"
)


class WeatherError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _condition(code: Any, is_day: Any = 1) -> dict[str, Any]:
    wid, main, desc, icon = _WMO.get(int(code) if code is not None else 0, _WMO[0])
    suffix = "d" if is_day in (1, True, None) else "n"
    return {"id": wid, "main": main, "description": desc, "icon": f"{icon}{suffix}"}


def _epoch(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        return int(datetime.fromisoformat(iso).timestamp())
    except ValueError:
        return None


def _european_aqi_to_index(aqi: float | None) -> int:
    """OpenWeather's 1 (good) .. 5 (very poor) scale from the European AQI."""
    if aqi is None:
        return 1
    for limit, index in ((20, 1), (40, 2), (60, 3), (80, 4)):
        if aqi <= limit:
            return index
    return 5


class WeatherService:
    def _cache_key(self, namespace: str, *parts: Any) -> str:
        raw = ":".join(str(p) for p in parts)
        digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return f"weather:om:{namespace}:{digest}"

    def _get(self, url: str, params: dict[str, Any], cache_key: str, ttl: int) -> Any:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            response = requests.get(
                url, params=params, timeout=12, headers={"User-Agent": USER_AGENT}
            )
        except requests.RequestException as exc:
            logger.warning("Weather request failed: %s", exc)
            raise WeatherError("Weather service unavailable.", status_code=503) from exc
        if response.status_code == 429:
            raise WeatherError("Weather rate limit exceeded. Try again shortly.", status_code=429)
        if not response.ok:
            logger.warning("Weather upstream %s returned %s", url, response.status_code)
            raise WeatherError("Weather upstream error.", status_code=502)
        data = response.json()
        cache.set(cache_key, data, ttl)
        return data

    # --- raw Open-Meteo calls -------------------------------------------------

    def _current_raw(self, lats: list[float], lons: list[float]) -> list[dict[str, Any]]:
        key = self._cache_key("current", ",".join(f"{a:.3f}" for a in lats), ",".join(f"{o:.3f}" for o in lons))
        data = self._get(
            FORECAST_URL,
            {
                "latitude": ",".join(str(round(a, 4)) for a in lats),
                "longitude": ",".join(str(round(o, 4)) for o in lons),
                "current": _CURRENT_VARS,
                "daily": "sunrise,sunset,temperature_2m_min,temperature_2m_max",
                "forecast_days": 1,
                "timezone": "auto",
                "wind_speed_unit": "ms",
                "timeformat": "unixtime",
            },
            key,
            CACHE_TTL["current"],
        )
        return data if isinstance(data, list) else [data]

    @staticmethod
    def _to_owm_current(raw: dict[str, Any], lat: float, lon: float) -> dict[str, Any]:
        cur = raw.get("current") or {}
        daily = raw.get("daily") or {}
        first = lambda key: (daily.get(key) or [None])[0]  # noqa: E731
        rain_mm = (cur.get("rain") or 0) + (cur.get("showers") or 0)
        snow_mm = (cur.get("snowfall") or 0) * 10  # cm -> mm (water-ish equivalent)
        payload: dict[str, Any] = {
            "coord": {"lat": lat, "lon": lon},
            "dt": cur.get("time"),
            "weather": [_condition(cur.get("weather_code"), cur.get("is_day"))],
            "main": {
                "temp": cur.get("temperature_2m"),
                "feels_like": cur.get("apparent_temperature"),
                "pressure": cur.get("pressure_msl"),
                "humidity": cur.get("relative_humidity_2m"),
                "temp_min": first("temperature_2m_min"),
                "temp_max": first("temperature_2m_max"),
            },
            "visibility": cur.get("visibility"),
            "uvi": cur.get("uv_index"),
            "clouds": {"all": cur.get("cloud_cover")},
            "wind": {"speed": cur.get("wind_speed_10m"), "deg": cur.get("wind_direction_10m")},
            "sys": {"sunrise": first("sunrise"), "sunset": first("sunset")},
            "timezone": raw.get("utc_offset_seconds", 0),
            "name": "",
            "_source": "open-meteo",
        }
        if rain_mm:
            payload["rain"] = {"1h": rain_mm}
        if snow_mm:
            payload["snow"] = {"1h": snow_mm}
        return payload

    # --- public API (same method names and shapes as the old OpenWeather service) --

    def current(self, lat: float, lon: float) -> dict[str, Any]:
        return self._to_owm_current(self._current_raw([lat], [lon])[0], lat, lon)

    def forecast(self, lat: float, lon: float) -> dict[str, Any]:
        """5-day forecast in 3-hour steps, shaped like OpenWeather /forecast."""
        key = self._cache_key("forecast", round(lat, 3), round(lon, 3))
        raw = self._get(
            FORECAST_URL,
            {
                "latitude": round(lat, 4),
                "longitude": round(lon, 4),
                "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,"
                "weather_code,wind_speed_10m,is_day",
                "forecast_days": 5,
                "timezone": "auto",
                "wind_speed_unit": "ms",
            },
            key,
            CACHE_TTL["forecast"],
        )
        hourly = raw.get("hourly") or {}
        times = hourly.get("time") or []
        now = time.time()
        items = []
        for i in range(0, len(times), 3):
            dt = _epoch(times[i])
            if dt is None or dt < now - 3600:
                continue
            temp = (hourly.get("temperature_2m") or [None])[i]
            pop = (hourly.get("precipitation_probability") or [None])[i]
            items.append(
                {
                    "dt": dt,
                    "dt_txt": times[i].replace("T", " ") + ":00",
                    "main": {
                        "temp": temp,
                        "temp_min": temp,
                        "temp_max": temp,
                        "humidity": (hourly.get("relative_humidity_2m") or [None])[i],
                    },
                    "weather": [
                        _condition(
                            (hourly.get("weather_code") or [0])[i],
                            (hourly.get("is_day") or [1])[i],
                        )
                    ],
                    "wind": {"speed": (hourly.get("wind_speed_10m") or [None])[i]},
                    "pop": (pop or 0) / 100,
                }
            )
        return {"list": items, "city": {"timezone": raw.get("utc_offset_seconds", 0)}}

    def onecall(self, lat: float, lon: float) -> dict[str, Any]:
        key = self._cache_key("onecall", round(lat, 3), round(lon, 3))
        cached = cache.get(key)
        if cached is not None:
            return cached
        current = self.current(lat, lon)
        forecast = self.forecast(lat, lon)
        payload = {
            "lat": lat,
            "lon": lon,
            "timezone": forecast.get("city", {}).get("timezone", 0),
            "current": self._normalize_current(current),
            "hourly": self._normalize_hourly(forecast),
            "daily": self._normalize_daily(forecast),
            "alerts": [],
            "_source": "open-meteo",
        }
        cache.set(key, payload, CACHE_TTL["onecall"])
        return payload

    def air_pollution(self, lat: float, lon: float) -> dict[str, Any]:
        key = self._cache_key("air", round(lat, 3), round(lon, 3))
        raw = self._get(
            AIR_URL,
            {
                "latitude": round(lat, 4),
                "longitude": round(lon, 4),
                "current": "european_aqi,pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,"
                "sulphur_dioxide,ozone",
                "timeformat": "unixtime",
            },
            key,
            CACHE_TTL["air"],
        )
        cur = raw.get("current") or {}
        return {
            "coord": {"lat": lat, "lon": lon},
            "list": [
                {
                    "dt": cur.get("time"),
                    "main": {"aqi": _european_aqi_to_index(cur.get("european_aqi"))},
                    "components": {
                        "co": cur.get("carbon_monoxide"),
                        "no2": cur.get("nitrogen_dioxide"),
                        "o3": cur.get("ozone"),
                        "so2": cur.get("sulphur_dioxide"),
                        "pm2_5": cur.get("pm2_5"),
                        "pm10": cur.get("pm10"),
                    },
                }
            ],
        }

    def geocode(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        key = self._cache_key("geocode", query.lower(), limit)
        raw = self._get(
            GEOCODE_URL,
            {"name": query, "count": limit, "language": "en", "format": "json"},
            key,
            CACHE_TTL["geocode"],
        )
        return [
            {
                "name": item.get("name", ""),
                "lat": item.get("latitude"),
                "lon": item.get("longitude"),
                "country": item.get("country_code", ""),
                "state": item.get("admin1", ""),
            }
            for item in (raw.get("results") or [])
        ]

    def reverse_geocode(self, lat: float, lon: float, limit: int = 1) -> list[dict[str, Any]]:
        key = self._cache_key("reverse", round(lat, 3), round(lon, 3))
        raw = self._get(
            REVERSE_URL,
            {"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 10, "accept-language": "en"},
            key,
            CACHE_TTL["reverse"],
        )
        address = raw.get("address") or {}
        name = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
            or address.get("county")
            or raw.get("name")
            or ""
        )
        if not name:
            return []
        return [
            {
                "name": name,
                "lat": lat,
                "lon": lon,
                "country": (address.get("country_code") or "").upper(),
                "state": address.get("state", ""),
            }
        ][:limit]

    def tile_png(self, layer: str, z: int, x: int, y: int) -> bytes:
        # Raster weather tiles were an OpenWeather-only (keyed) feature and the
        # frontend no longer requests them; return a blank tile.
        return _TRANSPARENT_PNG

    def grid_snapshot(
        self, lat_min: float, lat_max: float, lon_min: float, lon_max: float, step: int = 3
    ) -> list[dict[str, Any]]:
        step = max(2, min(step, 6))
        key = self._cache_key("grid", lat_min, lat_max, lon_min, lon_max, step)
        cached = cache.get(key)
        if cached is not None:
            return cached

        coords: list[tuple[float, float]] = []
        lat = lat_min
        while lat <= lat_max:
            lon = lon_min
            while lon <= lon_max:
                coords.append((lat, lon))
                lon += step
            lat += step

        points: list[dict[str, Any]] = []
        # Open-Meteo accepts many coordinates per request; batch to keep calls low.
        for start in range(0, len(coords), 50):
            batch = coords[start : start + 50]
            try:
                raws = self._current_raw([c[0] for c in batch], [c[1] for c in batch])
            except WeatherError:
                continue
            for (plat, plon), raw in zip(batch, raws):
                current = self._to_owm_current(raw, plat, plon)
                points.append(self._normalize_current(current) | {"lat": plat, "lon": plon})

        cache.set(key, points, CACHE_TTL["grid"])
        return points

    def summary(self, lat: float, lon: float) -> dict[str, Any]:
        key = self._cache_key("summary", round(lat, 3), round(lon, 3))
        cached = cache.get(key)
        if cached is not None:
            return cached

        onecall = self.onecall(lat, lon)
        try:
            air = self.air_pollution(lat, lon)
        except WeatherError:
            air = None
        try:
            places = self.reverse_geocode(lat, lon, limit=1)
        except WeatherError:
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

    # --- normalisers (unchanged from the OpenWeather version) ------------------

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
            values_min = [v for v in (slot.get("temp_min"), main.get("temp_min")) if v is not None]
            values_max = [v for v in (slot.get("temp_max"), main.get("temp_max")) if v is not None]
            slot["temp_min"] = min(values_min) if values_min else None
            slot["temp_max"] = max(values_max) if values_max else None
            slot["pop"] = max(slot.get("pop", 0) or 0, entry.get("pop", 0) or 0)
        return list(by_day.values())[:7]
