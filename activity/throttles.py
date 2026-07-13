from duo_project.throttling import FailOpenUserRateThrottle


class ActivityRateThrottle(FailOpenUserRateThrottle):
    rate = "120/min"
