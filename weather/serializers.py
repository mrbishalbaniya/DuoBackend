from rest_framework import serializers


class LatLonSerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)


class GeocodeQuerySerializer(serializers.Serializer):
    q = serializers.CharField(min_length=1, max_length=120)
    limit = serializers.IntegerField(min_value=1, max_value=10, default=5, required=False)


class GridQuerySerializer(serializers.Serializer):
    lat_min = serializers.FloatField(min_value=-90, max_value=90)
    lat_max = serializers.FloatField(min_value=-90, max_value=90)
    lon_min = serializers.FloatField(min_value=-180, max_value=180)
    lon_max = serializers.FloatField(min_value=-180, max_value=180)
    step = serializers.IntegerField(min_value=2, max_value=8, default=3, required=False)

    def validate(self, attrs):
        if attrs["lat_min"] > attrs["lat_max"]:
            raise serializers.ValidationError("lat_min must be <= lat_max")
        if attrs["lon_min"] > attrs["lon_max"]:
            raise serializers.ValidationError("lon_min must be <= lon_max")
        span = (attrs["lat_max"] - attrs["lat_min"]) * (attrs["lon_max"] - attrs["lon_min"])
        if span > 400:
            raise serializers.ValidationError("Grid bbox too large")
        return attrs
