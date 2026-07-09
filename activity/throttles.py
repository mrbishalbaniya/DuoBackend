from rest_framework.throttling import UserRateThrottle


class ActivityRateThrottle(UserRateThrottle):
    rate = "120/min"
