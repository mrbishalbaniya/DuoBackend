from duo_project.throttling import FailOpenAnonRateThrottle, FailOpenUserRateThrottle


class VerificationHandoffThrottle(FailOpenAnonRateThrottle):
    scope = "verification_handoff"


class PhotoUploadBurstThrottle(FailOpenUserRateThrottle):
    """Stops rapid-fire uploads (scripts, runaway client retries)."""

    scope = "photo_upload_burst"


class PhotoUploadDailyThrottle(FailOpenUserRateThrottle):
    """Caps daily AI-verification + storage cost per user."""

    scope = "photo_upload_daily"


# Backwards-compatible alias for existing imports.
PhotoUploadThrottle = PhotoUploadBurstThrottle
