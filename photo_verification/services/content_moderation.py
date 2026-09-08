"""Local, offline content-safety moderation. No third-party API calls.

- NSFW/nudity: NudeNet (ONNX, offline, MIT-licensed) — a pretrained detector,
  not a service call. Model weights download once on first use, same pattern
  as the InsightFace integration in ml/insightface_engine.py.
- Violence/weapons/hate-symbols/drugs/non-photo content (screenshots, memes,
  ads, QR codes): best-effort zero-shot classification via CLIP. Weaker than
  a specialized model — see the "Limitations" note in the project plan.

Fails closed: if a model can't load or errors, the result is UNAVAILABLE,
which callers must route to MANUAL_REVIEW — never silently treated as safe.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

import cv2
import numpy as np

logger = logging.getLogger("duo.content_moderation")

from photo_verification.constants import (
    CLIP_UNSAFE_REJECT_MARGIN,
    CLIP_UNSAFE_REVIEW_MARGIN,
    NSFW_EXPLICIT_REJECT_THRESHOLD,
    NSFW_EXPLICIT_REVIEW_THRESHOLD,
    NSFW_REVIEW_LABEL_REJECT_THRESHOLD,
    ModerationStatus,
    RejectionCategory,
)


@dataclass(frozen=True)
class ContentModerationResult:
    status: ModerationStatus  # APPROVED | REJECTED | MANUAL_REVIEW
    category: RejectionCategory
    friendly_reason: str  # safe to show users; empty when status == APPROVED
    detail: str = ""  # internal-only, for logs/admin — never sent to the client
    signals: dict = field(default_factory=dict)  # internal-only debugging metadata


_SAFE_RESULT = ContentModerationResult(
    status=ModerationStatus.APPROVED,
    category=RejectionCategory.OTHER,
    friendly_reason="",
)

# NudeNet label -> always safe (normal swimwear/beach/gym/cultural clothing,
# shirtless men, faces, feet, belly, armpits — covered or not).
_NUDENET_SAFE_LABELS = {
    "FACE_FEMALE",
    "FACE_MALE",
    "FEET_EXPOSED",
    "FEET_COVERED",
    "BELLY_EXPOSED",
    "BELLY_COVERED",
    "ARMPITS_EXPOSED",
    "ARMPITS_COVERED",
    "MALE_BREAST_EXPOSED",
    "FEMALE_GENITALIA_COVERED",
    "FEMALE_BREAST_COVERED",
    "BUTTOCKS_COVERED",
    "ANUS_COVERED",
}
# Unambiguous — never a false positive from swimwear/beach photos.
_NUDENET_HARD_REJECT_LABELS = {
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_EXPOSED",
}
# Context-dependent (thong swimwear, breastfeeding, etc.) — a human decides,
# never auto-rejected on this signal alone.
_NUDENET_REVIEW_LABELS = {
    "BUTTOCKS_EXPOSED",
    "FEMALE_BREAST_EXPOSED",
}

_nude_detector = None
_nude_detector_checked = False
_nude_detector_lock = threading.Lock()


def _get_nude_detector():
    global _nude_detector, _nude_detector_checked
    # Fast path: no lock once loaded (the common case for every request after
    # the first). The lock only matters during the ~seconds-long cold start.
    if _nude_detector_checked:
        return _nude_detector
    with _nude_detector_lock:
        # Re-check inside the lock: another thread may have finished loading
        # (or failed) while we were waiting for it — without this, concurrent
        # requests during cold start (e.g. the parallel photo-upload feature,
        # which uploads up to 3 photos at once) would each see the model as
        # "unavailable" instead of waiting for the one load in progress.
        if _nude_detector_checked:
            return _nude_detector
        try:
            from nudenet import NudeDetector

            _nude_detector = NudeDetector()
        except Exception:
            logger.exception("nudenet_detector_load_failed")
            _nude_detector = None
        finally:
            _nude_detector_checked = True
    return _nude_detector


def _rgb_to_jpeg_bytes(rgb: np.ndarray) -> bytes:
    bgr = rgb[:, :, ::-1]
    ok, buf = cv2.imencode(".jpg", bgr)
    if not ok:
        raise ValueError("Could not encode image for moderation.")
    return buf.tobytes()


def check_nsfw(rgb: np.ndarray) -> ContentModerationResult:
    detector = _get_nude_detector()
    if detector is None:
        return ContentModerationResult(
            status=ModerationStatus.MANUAL_REVIEW,
            category=RejectionCategory.NUDITY,
            friendly_reason="We couldn't finish checking this photo. It's been sent for review.",
            detail="NudeNet model unavailable.",
        )

    try:
        detections = detector.detect(_rgb_to_jpeg_bytes(rgb))
    except Exception as exc:
        logger.exception("nudenet_detection_failed")
        return ContentModerationResult(
            status=ModerationStatus.MANUAL_REVIEW,
            category=RejectionCategory.NUDITY,
            friendly_reason="We couldn't finish checking this photo. It's been sent for review.",
            detail=f"NudeNet detection failed: {exc}",
        )

    best_reject_score = 0.0
    best_review_score = 0.0
    for d in detections:
        label = d.get("class")
        score = float(d.get("score", 0.0))
        if label in _NUDENET_HARD_REJECT_LABELS:
            best_reject_score = max(best_reject_score, score)
        elif label in _NUDENET_REVIEW_LABELS:
            best_review_score = max(best_review_score, score)

    if best_reject_score >= NSFW_EXPLICIT_REJECT_THRESHOLD or best_review_score >= NSFW_REVIEW_LABEL_REJECT_THRESHOLD:
        return ContentModerationResult(
            status=ModerationStatus.REJECTED,
            category=RejectionCategory.NUDITY,
            friendly_reason="This photo contains content that isn't allowed on profile photos.",
            detail=f"NudeNet explicit-class score reject={best_reject_score:.2f} review_label={best_review_score:.2f}",
            signals={"nudenet_reject_score": best_reject_score, "nudenet_review_score": best_review_score},
        )
    if best_reject_score >= NSFW_EXPLICIT_REVIEW_THRESHOLD or best_review_score >= NSFW_EXPLICIT_REVIEW_THRESHOLD:
        return ContentModerationResult(
            status=ModerationStatus.MANUAL_REVIEW,
            category=RejectionCategory.NUDITY,
            friendly_reason="This photo needs a quick manual review before it can be approved.",
            detail=f"NudeNet borderline scores reject={best_reject_score:.2f} review={best_review_score:.2f}",
            signals={"nudenet_reject_score": best_reject_score, "nudenet_review_score": best_review_score},
        )
    return _SAFE_RESULT


# --- Best-effort violence/weapons/hate/drugs/non-photo via CLIP zero-shot ---
# Weaker than a specialized model — see plan Limitations. Uncertain margins
# always route to MANUAL_REVIEW rather than guessing.

_SAFE_PROMPTS = [
    "a normal photo of a person",
    "a portrait photo of a person",
    "a selfie photo",
    "a photo of a person outdoors",
    "a photo of a person at the beach in swimwear",
    "a photo of a person at the gym",
    "a photo of a person in traditional clothing",
    "a group photo of friends",
]

# Each entry: (RejectionCategory, [unsafe prompts], friendly reason)
_UNSAFE_PROMPT_SETS: list[tuple[RejectionCategory, list[str], str]] = [
    (
        RejectionCategory.VIOLENCE,
        [
            "graphic violence and gore",
            "a dead body or severe injury",
            "a photo of blood and injury",
        ],
        "This photo contains graphic or violent content that isn't allowed.",
    ),
    (
        RejectionCategory.WEAPON,
        [
            "a person holding a gun or weapon in a threatening way",
            "a photo of firearms or weapons",
        ],
        "This photo contains weapons or threatening imagery that isn't allowed.",
    ),
    (
        RejectionCategory.HATE_SYMBOL,
        [
            "a hate symbol or extremist propaganda",
            "a Nazi or extremist flag or symbol",
        ],
        "This photo contains symbols that aren't allowed on profile photos.",
    ),
    (
        RejectionCategory.DRUGS,
        [
            "illegal drugs for sale",
            "a photo of drug paraphernalia or drug use",
        ],
        "This photo contains content related to illegal drugs that isn't allowed.",
    ),
    (
        RejectionCategory.NON_PHOTO_CONTENT,
        [
            "a screenshot of a phone or computer screen",
            "a meme with text captions",
            "an advertisement or promotional poster",
            "a black and white QR code",
            "a pixelated square barcode pattern for scanning",
            "a printed QR code on paper or a screen",
            "a phone app screen showing a QR code to scan",
            "a messaging app screenshot with a QR code",
            "a business card with contact information",
            "a company logo or cartoon illustration",
        ],
        "Please upload a real photo of yourself, not a screenshot, meme, or ad.",
    ),
]

_clip_bundle = None
_clip_checked = False
_clip_bundle_lock = threading.Lock()


def _get_clip_bundle():
    global _clip_bundle, _clip_checked
    if _clip_checked:
        return _clip_bundle
    with _clip_bundle_lock:
        # Same race-condition guard as _get_nude_detector: without
        # re-checking inside the lock, a concurrent request arriving during
        # the (multi-second) cold-load would see _clip_checked already True
        # and return the still-empty bundle instead of waiting for it.
        if _clip_checked:
            return _clip_bundle
        try:
            import open_clip
            import torch

            model, _, preprocess = open_clip.create_model_and_transforms(
                "ViT-B-32-quickgelu", pretrained="openai"
            )
            tokenizer = open_clip.get_tokenizer("ViT-B-32-quickgelu")
            model.eval()

            with torch.no_grad():
                safe_features = model.encode_text(tokenizer(_SAFE_PROMPTS))
                safe_features /= safe_features.norm(dim=-1, keepdim=True)

                unsafe_features_by_category = {}
                for category, prompts, _reason in _UNSAFE_PROMPT_SETS:
                    feats = model.encode_text(tokenizer(prompts))
                    feats /= feats.norm(dim=-1, keepdim=True)
                    unsafe_features_by_category[category] = feats

            _clip_bundle = {
                "model": model,
                "preprocess": preprocess,
                "torch": torch,
                "safe_features": safe_features,
                "unsafe_features_by_category": unsafe_features_by_category,
            }
        except Exception:
            logger.exception("clip_bundle_load_failed")
            _clip_bundle = None
        finally:
            _clip_checked = True
    return _clip_bundle


def check_unsafe_content(rgb: np.ndarray) -> ContentModerationResult:
    bundle = _get_clip_bundle()
    if bundle is None:
        return ContentModerationResult(
            status=ModerationStatus.MANUAL_REVIEW,
            category=RejectionCategory.OTHER,
            friendly_reason="We couldn't finish checking this photo. It's been sent for review.",
            detail="CLIP model unavailable.",
        )

    try:
        from PIL import Image

        torch = bundle["torch"]
        image = Image.fromarray(rgb)
        image_input = bundle["preprocess"](image).unsqueeze(0)

        with torch.no_grad():
            image_features = bundle["model"].encode_image(image_input)
            image_features /= image_features.norm(dim=-1, keepdim=True)
            safe_score = float((image_features @ bundle["safe_features"].T).max())

            best_category = None
            best_margin = -1.0
            best_unsafe_score = 0.0
            for category, _prompts, _reason in _UNSAFE_PROMPT_SETS:
                unsafe_feats = bundle["unsafe_features_by_category"][category]
                unsafe_score = float((image_features @ unsafe_feats.T).max())
                margin = unsafe_score - safe_score
                if margin > best_margin:
                    best_margin = margin
                    best_category = category
                    best_unsafe_score = unsafe_score
    except Exception as exc:
        logger.exception("clip_classification_failed")
        return ContentModerationResult(
            status=ModerationStatus.MANUAL_REVIEW,
            category=RejectionCategory.OTHER,
            friendly_reason="We couldn't finish checking this photo. It's been sent for review.",
            detail=f"CLIP classification failed: {exc}",
        )

    friendly_reason = next(
        (reason for cat, _prompts, reason in _UNSAFE_PROMPT_SETS if cat == best_category),
        "This photo needs a quick manual review before it can be approved.",
    )
    signals = {"clip_margin": best_margin, "clip_unsafe_score": best_unsafe_score, "clip_safe_score": safe_score}

    if best_margin >= CLIP_UNSAFE_REJECT_MARGIN:
        return ContentModerationResult(
            status=ModerationStatus.REJECTED,
            category=best_category or RejectionCategory.OTHER,
            friendly_reason=friendly_reason,
            detail=f"CLIP category={best_category} margin={best_margin:.3f}",
            signals=signals,
        )
    if best_margin >= CLIP_UNSAFE_REVIEW_MARGIN:
        return ContentModerationResult(
            status=ModerationStatus.MANUAL_REVIEW,
            category=best_category or RejectionCategory.OTHER,
            friendly_reason="This photo needs a quick manual review before it can be approved.",
            detail=f"CLIP category={best_category} margin={best_margin:.3f}",
            signals=signals,
        )
    return _SAFE_RESULT


def moderate_content(rgb: np.ndarray) -> ContentModerationResult:
    """Run all local content-safety checks. NSFW first (highest-confidence,
    highest-stakes signal); if it already flags something, don't bother
    running the weaker best-effort CLIP pass — return the stronger verdict."""
    nsfw_result = check_nsfw(rgb)
    if nsfw_result.status != ModerationStatus.APPROVED:
        return nsfw_result
    return check_unsafe_content(rgb)
