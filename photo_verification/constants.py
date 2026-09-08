"""Thresholds and weights for profile photo verification."""

from enum import Enum


class PhotoStatus(str, Enum):
    APPROVED = "APPROVED"
    WARNING = "WARNING"
    REJECTED = "REJECTED"


class ModerationStatus(str, Enum):
    """Workflow status of a ProfilePhoto — distinct from PhotoStatus (quality/
    authenticity verdict). This is the one and only status that gates whether
    a photo may ever appear to other users."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class RejectionCategory(str, Enum):
    """Internal-only classification of why a photo was rejected/flagged.
    Never sent to the client — only a friendly, generic reason is."""

    NUDITY = "nudity"
    VIOLENCE = "violence"
    WEAPON = "weapon"
    HATE_SYMBOL = "hate_symbol"
    DRUGS = "drugs"
    NON_PHOTO_CONTENT = "non_photo_content"  # screenshot/meme/ad/QR/logo
    QUALITY = "quality"  # existing pipeline: blur/dark/duplicate/no-face/AI-gen
    OTHER = "other"


# Resolution
MIN_IMAGE_WIDTH = 400
MIN_IMAGE_HEIGHT = 400

# Blur — Laplacian variance (higher = sharper)
BLUR_REJECT_THRESHOLD = 50.0
BLUR_WARNING_THRESHOLD = 120.0

# Brightness — mean grayscale 0–255
BRIGHTNESS_LOW_WARNING = 45.0
BRIGHTNESS_HIGH_WARNING = 210.0

# AI-generated probability (multi-signal ensemble; see ai_detection.py)
AI_FLAG_THRESHOLD = 0.72
AI_REJECT_THRESHOLD = 0.88

# Duplicate similarity (0–1 cosine on perceptual hash bits)
DUPLICATE_FLAG_THRESHOLD = 0.72
DUPLICATE_REJECT_THRESHOLD = 0.92

# Face centering — max distance from image center (fraction of half-diagonal)
FACE_CENTER_MAX_OFFSET = 0.35

# Quality score weights (sum = 100)
WEIGHT_FACE_DETECTED = 30
WEIGHT_SINGLE_FACE = 20
WEIGHT_GOOD_QUALITY = 20
WEIGHT_GOOD_BRIGHTNESS = 10
WEIGHT_GOOD_RESOLUTION = 10
WEIGHT_CENTERED_FACE = 10


# --- Content safety moderation (local, offline — no third-party API) ---

# NudeNet per-class exposure score (0-1) above which we hard-reject.
# Kept high-confidence-only for genuinely explicit classes so normal
# swimwear/beach/gym photos are never caught.
NSFW_EXPLICIT_REJECT_THRESHOLD = 0.55
# Lower band on the same explicit classes -> uncertain, not auto-rejected.
NSFW_EXPLICIT_REVIEW_THRESHOLD = 0.35
# Context-dependent labels (BUTTOCKS_EXPOSED, FEMALE_BREAST_EXPOSED — could be
# swimwear) stay review-only at low/medium confidence, but a very high score
# here means unambiguous full nudity (not a beach photo) and should still
# auto-reject rather than sit in manual review forever.
NSFW_REVIEW_LABEL_REJECT_THRESHOLD = 0.75

# CLIP zero-shot similarity margin (unsafe-prompt score minus best safe-prompt
# score) above which we treat a category as detected.
CLIP_UNSAFE_REJECT_MARGIN = 0.08
CLIP_UNSAFE_REVIEW_MARGIN = 0.03


# --- Selfie verification & face matching ---

class VerificationStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    UNDER_REVIEW = "UNDER_REVIEW"


LIVENESS_STEPS = ("smile", "blink")

# Cosine similarity thresholds
SIMILARITY_VERIFIED = 0.80
SIMILARITY_REVIEW = 0.65

# Fraud probability thresholds
FRAUD_REJECT = 0.90
FRAUD_REVIEW = 0.70

# Liveness aggregate pass threshold (0–1)
LIVENESS_PASS_THRESHOLD = 0.75

# Per-step liveness validation (relative to neutral baseline frame)
SMILE_MOUTH_DELTA_MIN = 0.07
SMILE_MOUTH_RATIO_MIN = 1.20
SMILE_CORNER_LIFT_MIN = 0.008  # fraction of face width

BLINK_EAR_RATIO_MAX = 0.82  # current EAR / baseline EAR (eyes more closed)
BLINK_EAR_DELTA_MIN = 0.03
BLINK_EAR_STRONG_DROP = 0.055  # passes even if ratio is borderline

HEAD_YAW_DELTA_MIN = 0.08

# Verification session TTL (minutes)
VERIFICATION_SESSION_TTL_MINUTES = 30
