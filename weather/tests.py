from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from weather.services.openmeteo import WeatherService, _condition, _european_aqi_to_index

OPEN_METEO_CURRENT = {
    "utc_offset_seconds": 20700,
    "current": {
        "time": 1_759_000_000,
        "temperature_2m": 21.5,
        "relative_humidity_2m": 60,
        "apparent_temperature": 21.0,
        "is_day": 1,
        "rain": 0.4,
        "showers": 0.0,
        "snowfall": 0.0,
        "weather_code": 61,
        "cloud_cover": 80,
        "pressure_msl": 1012,
        "wind_speed_10m": 3.2,
        "wind_direction_10m": 180,
        "visibility": 10000,
        "uv_index": 4,
    },
    "daily": {"sunrise": [1_758_990_000], "sunset": [1_759_033_000], "temperature_2m_min": [16], "temperature_2m_max": [25]},
}


class FakeResponse:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status
        self.ok = status < 400

    def json(self):
        return self._data


class OpenMeteoServiceTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_conditions_map_to_openweather_codes(self):
        self.assertEqual(_condition(0, 1)["icon"], "01d")
        self.assertEqual(_condition(95, 0)["main"], "Thunderstorm")
        self.assertEqual(_european_aqi_to_index(15), 1)
        self.assertEqual(_european_aqi_to_index(95), 5)

    @patch("weather.services.openmeteo.requests.get", return_value=FakeResponse(OPEN_METEO_CURRENT))
    def test_current_uses_openweather_shape_without_key(self, mock_get):
        data = WeatherService().current(27.7, 85.3)
        self.assertEqual(data["main"]["temp"], 21.5)
        self.assertEqual(data["weather"][0]["main"], "Rain")
        self.assertEqual(data["rain"], {"1h": 0.4})
        params = mock_get.call_args.kwargs["params"]
        self.assertNotIn("appid", params)

    @patch("weather.services.openmeteo.requests.get", return_value=FakeResponse(OPEN_METEO_CURRENT))
    def test_current_endpoint_works_without_api_key(self, _mock_get):
        user = get_user_model().objects.create_user(username="w.user", email="w@example.com", password="StrongPass!234")
        self.client.force_authenticate(user)
        response = self.client.get("/api/weather/current/", {"lat": 27.7, "lon": 85.3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["main"]["humidity"], 60)
