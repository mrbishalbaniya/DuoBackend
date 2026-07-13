from rest_framework.throttling import UserRateThrottle


class CallRateThrottle(UserRateThrottle):
    scope = "calls"
