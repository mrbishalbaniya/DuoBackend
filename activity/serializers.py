from rest_framework import serializers


class ActivityGridQuerySerializer(serializers.Serializer):
    lat_min = serializers.FloatField(min_value=-90, max_value=90)
    lat_max = serializers.FloatField(min_value=-90, max_value=90)
    lon_min = serializers.FloatField(min_value=-180, max_value=180)
    lon_max = serializers.FloatField(min_value=-180, max_value=180)
    zoom = serializers.FloatField(min_value=0, max_value=22, default=4, required=False)
    step = serializers.FloatField(min_value=0.05, max_value=12, default=1.0, required=False)

    def validate(self, attrs):
        if attrs["lat_min"] > attrs["lat_max"]:
            raise serializers.ValidationError("lat_min must be <= lat_max")
        if attrs["lon_min"] > attrs["lon_max"]:
            raise serializers.ValidationError("lon_min must be <= lon_max")
        span = (attrs["lat_max"] - attrs["lat_min"]) * (attrs["lon_max"] - attrs["lon_min"])
        if span > 12000:
            raise serializers.ValidationError("Grid bbox too large")
        return attrs
