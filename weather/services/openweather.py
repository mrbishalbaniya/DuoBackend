"""Backwards-compatible names for the weather service.

Weather now comes from Open-Meteo (free, no API key). See openmeteo.py.
"""
from .openmeteo import CACHE_TTL, WeatherError, WeatherService

OpenWeatherError = WeatherError
OpenWeatherService = WeatherService

__all__ = ["CACHE_TTL", "OpenWeatherError", "OpenWeatherService", "WeatherError", "WeatherService"]
