from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class AuthRateThrottle(AnonRateThrottle):
    scope = "auth"


class UploadRateThrottle(UserRateThrottle):
    scope = "upload"


class SwipeRateThrottle(UserRateThrottle):
    scope = "swipe"
