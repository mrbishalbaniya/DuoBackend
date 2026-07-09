from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import GeocodeQuerySerializer, GridQuerySerializer, LatLonSerializer
from .services.openweather import OpenWeatherError, OpenWeatherService
from .throttles import WeatherRateThrottle


def _service() -> OpenWeatherService:
    return OpenWeatherService()


def _lat_lon_params():
    return [
        OpenApiParameter("lat", float, OpenApiParameter.QUERY, required=True),
        OpenApiParameter("lon", float, OpenApiParameter.QUERY, required=True),
    ]


class WeatherBaseView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [WeatherRateThrottle]


@extend_schema(tags=["Weather"], parameters=_lat_lon_params())
class CurrentWeatherView(WeatherBaseView):
    def get(self, request):
        ser = LatLonSerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        try:
            return Response(_service().current(**ser.validated_data))
        except OpenWeatherError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)


@extend_schema(tags=["Weather"], parameters=_lat_lon_params())
class ForecastWeatherView(WeatherBaseView):
    def get(self, request):
        ser = LatLonSerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        try:
            return Response(_service().forecast(**ser.validated_data))
        except OpenWeatherError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)


@extend_schema(tags=["Weather"], parameters=_lat_lon_params())
class OneCallWeatherView(WeatherBaseView):
    def get(self, request):
        ser = LatLonSerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        try:
            return Response(_service().onecall(**ser.validated_data))
        except OpenWeatherError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)


@extend_schema(tags=["Weather"], parameters=_lat_lon_params())
class AirPollutionView(WeatherBaseView):
    def get(self, request):
        ser = LatLonSerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        try:
            return Response(_service().air_pollution(**ser.validated_data))
        except OpenWeatherError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)


@extend_schema(tags=["Weather"])
class GeocodeView(WeatherBaseView):
    def get(self, request):
        ser = GeocodeQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        try:
            return Response(_service().geocode(ser.validated_data["q"], ser.validated_data.get("limit", 5)))
        except OpenWeatherError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)


@extend_schema(tags=["Weather"], parameters=_lat_lon_params())
class ReverseGeocodeView(WeatherBaseView):
    def get(self, request):
        ser = LatLonSerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        try:
            return Response(_service().reverse_geocode(**ser.validated_data))
        except OpenWeatherError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)


@extend_schema(tags=["Weather"], parameters=_lat_lon_params())
class WeatherSummaryView(WeatherBaseView):
    def get(self, request):
        ser = LatLonSerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        try:
            return Response(_service().summary(**ser.validated_data))
        except OpenWeatherError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)


@extend_schema(tags=["Weather"])
class WeatherGridView(WeatherBaseView):
    def get(self, request):
        ser = GridQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        try:
            return Response(_service().grid_snapshot(**ser.validated_data))
        except OpenWeatherError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)


@extend_schema(tags=["Weather"])
class WeatherTileView(WeatherBaseView):
    def get(self, request, layer: str, z: int, x: int, y: int):
        try:
            content = _service().tile_png(layer, z, x, y)
        except OpenWeatherError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)
        return HttpResponse(content, content_type="image/png")
