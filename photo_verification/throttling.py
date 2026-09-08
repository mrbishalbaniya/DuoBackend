from duo_project.throttling import FailOpenAnonRateThrottle, FailOpenUserRateThrottle


class VerificationHandoffThrottle(FailOpenAnonRateThrottle):
    scope = "verification_handoff"


class PhotoUploadThrottle(FailOpenUserRateThrottle):
    scope = "photo_upload"
