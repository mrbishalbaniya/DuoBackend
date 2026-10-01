"""Per-session liveness state: random challenge steps, timing, and identity continuity.

Hardening based on how major dating apps verify selfies:
- Random challenges: each session gets its own random subset/order of steps,
  so a pre-recorded video of a fixed "smile then blink" sequence won't pass.
- Identity continuity: every liveness frame is fingerprinted with a face
  embedding and the final selfie must be the same person as all of them. This
  stops "do the challenges live, then upload someone else's photo as selfie".
- Time limits: the challenges must be done in one short sitting and the selfie
  must follow right after, which blocks slow frame-by-frame replay attacks.

State lives in UserVerification.liveness_data under keys that start with "_",
next to the existing per-step results ("smile", "blink", ...).
"""

from __future__ import annotations

import random
from datetime import datetime

from django.utils import timezone

from photo_verification.constants import (
    LIVENESS_MAX_DURATION_SECONDS,
    LIVENESS_STEP_POOL,
    LIVENESS_STEPS_PER_SESSION,
    SAME_PERSON_MIN_SIMILARITY,
    SELFIE_MAX_DELAY_SECONDS,
)
from photo_verification.ml.insightface_engine import cosine_similarity, extract_face_embedding

STEPS_KEY = "_steps"
FRAMES_KEY = "_frames"
STARTED_KEY = "_started_at"
LAST_FRAME_KEY = "_last_frame_at"

# Cap stored fingerprints so the JSON column stays small (baseline + action per step).
MAX_STORED_FRAMES = LIVENESS_STEPS_PER_SESSION * 2 + 2


def ensure_session_steps(session) -> list[str]:
    """Return this session's challenge steps, choosing and saving them on first use."""
    data = dict(session.liveness_data or {})
    steps = data.get(STEPS_KEY)
    if isinstance(steps, list) and steps and all(s in LIVENESS_STEP_POOL for s in steps):
        return list(steps)

    rng = random.SystemRandom()
    # Always include one facial-expression step and one head-turn step, then
    # fill the rest randomly, and shuffle the order.
    expression = rng.choice(["smile", "blink"])
    turn = rng.choice(["head_left", "head_right"])
    rest = [s for s in LIVENESS_STEP_POOL if s not in (expression, turn)]
    chosen = [expression, turn] + rng.sample(rest, max(0, LIVENESS_STEPS_PER_SESSION - 2))
    rng.shuffle(chosen)

    data[STEPS_KEY] = chosen
    session.liveness_data = data
    session.save(update_fields=["liveness_data", "updated_at"])
    return chosen


def session_steps(liveness_data: dict) -> list[str]:
    steps = (liveness_data or {}).get(STEPS_KEY)
    return list(steps) if isinstance(steps, list) and steps else []


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def liveness_time_exceeded(liveness_data: dict) -> bool:
    """True when the challenges have been going on for too long."""
    started = _parse((liveness_data or {}).get(STARTED_KEY))
    if not started:
        return False
    return (timezone.now() - started).total_seconds() > LIVENESS_MAX_DURATION_SECONDS


def record_frame(liveness_data: dict, rgb) -> dict:
    """Fingerprint a liveness frame and stamp timing. Returns updated liveness_data."""
    data = dict(liveness_data or {})
    now = timezone.now().isoformat()
    data.setdefault(STARTED_KEY, now)
    data[LAST_FRAME_KEY] = now

    emb = extract_face_embedding(rgb)
    if emb.embedding:
        frames = list(data.get(FRAMES_KEY) or [])
        frames.append({"embedding": [round(float(x), 5) for x in emb.embedding], "detector": emb.detector})
        data[FRAMES_KEY] = frames[-MAX_STORED_FRAMES:]
    return data


def identity_check(
    liveness_data: dict, selfie_embedding: list[float], selfie_detector: str
) -> tuple[bool, float, str]:
    """Check the selfie is the same person as every liveness frame.

    Returns (passed, lowest_similarity, reason). Only compares real biometric
    embeddings (InsightFace); with the weak OpenCV fallback it can't judge
    identity, and the engine already sends those sessions to manual review.
    """
    frames = [
        f for f in (liveness_data or {}).get(FRAMES_KEY) or []
        if f.get("embedding") and f.get("detector") == selfie_detector
    ]
    if not frames:
        return False, 0.0, "Liveness frames missing. Please redo the face challenges."
    if selfie_detector != "insightface" or not selfie_embedding:
        return True, 0.0, ""

    lowest = min(cosine_similarity(selfie_embedding, f["embedding"]) for f in frames)
    if lowest < SAME_PERSON_MIN_SIMILARITY:
        return False, lowest, "The selfie doesn't match the person who did the face challenges."
    return True, lowest, ""


def selfie_too_late(liveness_data: dict) -> bool:
    """True when the selfie comes too long after the last challenge frame."""
    last = _parse((liveness_data or {}).get(LAST_FRAME_KEY))
    if not last:
        return True
    return (timezone.now() - last).total_seconds() > SELFIE_MAX_DELAY_SECONDS
