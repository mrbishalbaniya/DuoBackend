from duo_project.throttling import FailOpenUserRateThrottle


class CallRateThrottle(FailOpenUserRateThrottle):
    scope = "calls"
