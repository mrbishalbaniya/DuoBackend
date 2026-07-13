from duo_project.throttling import FailOpenUserRateThrottle


class WeatherRateThrottle(FailOpenUserRateThrottle):
    scope = "weather"
