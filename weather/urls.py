from django.urls import path

from .views import (
    AirPollutionView,
    CurrentWeatherView,
    ForecastWeatherView,
    GeocodeView,
    OneCallWeatherView,
    ReverseGeocodeView,
    WeatherGridView,
    WeatherSummaryView,
    WeatherTileView,
)

urlpatterns = [
    path("current/", CurrentWeatherView.as_view(), name="weather-current"),
    path("forecast/", ForecastWeatherView.as_view(), name="weather-forecast"),
    path("onecall/", OneCallWeatherView.as_view(), name="weather-onecall"),
    path("air-pollution/", AirPollutionView.as_view(), name="weather-air"),
    path("geocode/", GeocodeView.as_view(), name="weather-geocode"),
    path("reverse-geocode/", ReverseGeocodeView.as_view(), name="weather-reverse-geocode"),
    path("summary/", WeatherSummaryView.as_view(), name="weather-summary"),
    path("grid/", WeatherGridView.as_view(), name="weather-grid"),
    path("tiles/<str:layer>/<int:z>/<int:x>/<int:y>.png", WeatherTileView.as_view(), name="weather-tile"),
]
