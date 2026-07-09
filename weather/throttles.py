from rest_framework.throttling import UserRateThrottle


class WeatherRateThrottle(UserRateThrottle):
    scope = "weather"
