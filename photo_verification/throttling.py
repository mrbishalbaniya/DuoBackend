from duo_project.throttling import FailOpenAnonRateThrottle


class VerificationHandoffThrottle(FailOpenAnonRateThrottle):
    scope = "verification_handoff"
