"""Thresholds and weights for profile photo verification."""

from enum import Enum


class PhotoStatus(str, Enum):
    APPROVED = "APPROVED"
    WARNING = "WARNING"
    REJECTED = "REJECTED"


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


# --- Selfie verification & face matching ---

class VerificationStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    UNDER_REVIEW = "UNDER_REVIEW"


LIVENESS_STEPS = ("smile", "blink", "head_left", "head_right")

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
