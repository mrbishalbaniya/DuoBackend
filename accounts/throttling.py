from duo_project.throttling import FailOpenAnonRateThrottle, FailOpenUserRateThrottle


class AuthRateThrottle(FailOpenAnonRateThrottle):
    scope = "auth"


class UploadRateThrottle(FailOpenUserRateThrottle):
    scope = "upload"


class SwipeRateThrottle(FailOpenUserRateThrottle):
    scope = "swipe"
