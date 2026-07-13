from rest_framework.throttling import AnonRateThrottle


class VerificationHandoffThrottle(AnonRateThrottle):
    scope = "verification_handoff"
