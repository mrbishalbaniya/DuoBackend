"""Liveness challenge validation (smile, blink, head turns)."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from photo_verification.constants import (
    BLINK_EAR_DELTA_MIN,
    BLINK_EAR_RATIO_MAX,
    BLINK_EAR_STRONG_DROP,
    HEAD_YAW_DELTA_MIN,
    LIVENESS_STEPS,
    SMILE_CORNER_LIFT_MIN,
    SMILE_MOUTH_DELTA_MIN,
    SMILE_MOUTH_RATIO_MIN,
)
from photo_verification.ml.insightface_engine import _get_insightface_app

# MediaPipe Face Mesh landmark indices
_LEFT_EYE = (33, 160, 158, 133, 153, 144)
_RIGHT_EYE = (362, 385, 387, 263, 373, 380)
_MOUTH_LEFT = 61
_MOUTH_RIGHT = 291
_UPPER_LIP = 13
_LOWER_LIP = 14
_LEFT_CHEEK = 234
_RIGHT_CHEEK = 454
_NOSE_TIP = 1

_face_mesh = None


def _get_face_mesh():
    global _face_mesh
    if _face_mesh is not None:
        return _face_mesh
    try:
        import mediapipe as mp

        if not hasattr(mp, "solutions"):
            return None
        _face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        return _face_mesh
    except Exception:
        return None


@dataclass(frozen=True)
class LivenessStepResult:
    step: str
    passed: bool
    score: float
    detail: str


def _eye_aspect_ratio(eye_pts: np.ndarray) -> float:
    if eye_pts.shape[0] < 6:
        return 0.0
    v1 = np.linalg.norm(eye_pts[1] - eye_pts[5])
    v2 = np.linalg.norm(eye_pts[2] - eye_pts[4])
    h = np.linalg.norm(eye_pts[0] - eye_pts[3])
    if h < 1e-6:
        return 0.0
    return float((v1 + v2) / (2.0 * h))


def _mouth_aspect_ratio(mouth_pts: np.ndarray) -> float:
    if mouth_pts.shape[0] < 4:
        return 0.0
    width = np.linalg.norm(mouth_pts[0] - mouth_pts[1])
    height = np.linalg.norm(mouth_pts[2] - mouth_pts[3])
    return float(height / (width + 1e-6))


def _head_yaw_from_kps(kps: np.ndarray) -> float:
    """Negative = left turn, positive = right turn (approximate)."""
    left_eye, right_eye, nose = kps[0], kps[1], kps[2]
    eye_mid_x = (left_eye[0] + right_eye[0]) / 2
    eye_dist = abs(right_eye[0] - left_eye[0]) + 1e-6
    return float((nose[0] - eye_mid_x) / eye_dist)


def _landmarks_to_array(landmarks, width: int, height: int) -> np.ndarray:
    return np.array(
        [[lm.x * width, lm.y * height] for lm in landmarks.landmark],
        dtype=np.float32,
    )


def _analyze_with_mediapipe(rgb: np.ndarray) -> dict | None:
    mesh = _get_face_mesh()
    if mesh is None:
        return None

    h, w = rgb.shape[:2]
    results = mesh.process(rgb)
    if not results.multi_face_landmarks:
        return None

    pts = _landmarks_to_array(results.multi_face_landmarks[0], w, h)
    left_eye = pts[list(_LEFT_EYE)]
    right_eye = pts[list(_RIGHT_EYE)]
    mouth = pts[[_MOUTH_LEFT, _MOUTH_RIGHT, _UPPER_LIP, _LOWER_LIP]]

    left_ear = _eye_aspect_ratio(left_eye)
    right_ear = _eye_aspect_ratio(right_eye)
    if left_ear <= 0 or right_ear <= 0:
        return None

    eye_ratio = float((left_ear + right_ear) / 2.0)
    mouth_open = _mouth_aspect_ratio(mouth)

    nose = pts[_NOSE_TIP]
    left_cheek, right_cheek = pts[_LEFT_CHEEK], pts[_RIGHT_CHEEK]
    face_mid_x = (left_cheek[0] + right_cheek[0]) / 2
    face_width = abs(right_cheek[0] - left_cheek[0]) + 1e-6
    yaw = float((nose[0] - face_mid_x) / face_width)

    mouth_corner_y = float((pts[_MOUTH_LEFT][1] + pts[_MOUTH_RIGHT][1]) / 2.0)

    return {
        "yaw": yaw,
        "mouth_open": mouth_open,
        "eye_ratio": eye_ratio,
        "mouth_corner_y": mouth_corner_y,
        "face_width": face_width,
        "face_detected": True,
        "source": "mediapipe",
    }


def _analyze_with_insightface(rgb: np.ndarray) -> dict | None:
    app = _get_insightface_app()
    if app is None:
        return None
    faces = app.get(rgb)
    if not faces:
        return None
    face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    if face.kps is None or len(face.kps) < 5:
        return None
    kps = np.asarray(face.kps, dtype=np.float32)
    return {
        "kps": kps,
        "yaw": _head_yaw_from_kps(kps),
        "mouth_open": float(
            np.linalg.norm(kps[3] - kps[4]) / (np.linalg.norm(kps[0] - kps[1]) + 1e-6)
        ),
        "face_detected": True,
        "source": "insightface",
    }


def _opencv_eye_aspect_ratio(eye_box, roi_h: int) -> float:
    _x, _y, ew, eh = eye_box
    if ew < 1 or eh < 1:
        return 0.0
    return float(eh / (ew + 1e-6))


def _analyze_with_opencv(rgb: np.ndarray) -> dict | None:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(80, 80))
    if len(faces) == 0:
        return None

    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    roi = gray[y : y + h, x : x + w]
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
    eyes = eye_cascade.detectMultiScale(roi, 1.1, 8)

    eye_ratio = None
    if len(eyes) >= 1:
        ears = [_opencv_eye_aspect_ratio(e, h) for e in eyes[:2]]
        eye_ratio = float(sum(ears) / len(ears))

    mouth_region = roi[int(h * 0.6) :, :]
    mouth_var = float(np.std(mouth_region)) if mouth_region.size else 0.0
    cx_face = x + w / 2
    cx_img = rgb.shape[1] / 2
    yaw = float((cx_face - cx_img) / (rgb.shape[1] / 2 + 1e-6))

    return {
        "yaw": yaw,
        "mouth_open": mouth_var / 80.0,
        "eye_ratio": eye_ratio,
        "face_detected": True,
        "eyes_detected": len(eyes) >= 1,
        "face_width": float(w),
        "source": "opencv",
    }


def _yaw_delta(metrics: dict, baseline: dict) -> float:
    """Positive = nose shifted right in frame (user turned to their left)."""
    return float(metrics.get("yaw", 0)) - float(baseline.get("yaw", 0))


def _analyze_frame(rgb: np.ndarray) -> dict | None:
    return _analyze_with_mediapipe(rgb) or _analyze_with_insightface(rgb) or _analyze_with_opencv(rgb)


def capture_baseline_metrics(rgb: np.ndarray) -> dict:
    metrics = _analyze_frame(rgb)
    return metrics or {}


def _corner_lift(metrics: dict, baseline: dict) -> float:
    base_y = baseline.get("mouth_corner_y")
    cur_y = metrics.get("mouth_corner_y")
    face_w = float(metrics.get("face_width") or baseline.get("face_width") or 1.0)
    if base_y is None or cur_y is None or face_w < 1:
        return 0.0
    return float((base_y - cur_y) / face_w)


def validate_liveness_step(step: str, rgb: np.ndarray, baseline: dict | None = None) -> LivenessStepResult:
    if step not in LIVENESS_STEPS:
        return LivenessStepResult(step=step, passed=False, score=0.0, detail="Unknown step")

    baseline = baseline or {}
    if not baseline:
        return LivenessStepResult(
            step=step,
            passed=False,
            score=0.0,
            detail="Neutral baseline not captured yet.",
        )

    metrics = _analyze_frame(rgb)
    if not metrics or not metrics.get("face_detected"):
        return LivenessStepResult(
            step=step,
            passed=False,
            score=0.0,
            detail="Face not detected. Center your face with good lighting.",
        )

    if step == "smile":
        mouth = metrics.get("mouth_open")
        base_mouth = baseline.get("mouth_open")
        if mouth is None or base_mouth is None:
            return LivenessStepResult(
                step=step,
                passed=False,
                score=0.0,
                detail="Could not read your mouth. Face the camera directly and try again.",
            )

        delta = float(mouth - base_mouth)
        ratio = float(mouth / (base_mouth + 1e-6))
        lift = _corner_lift(metrics, baseline)
        score = min(1.0, max(delta / SMILE_MOUTH_DELTA_MIN, ratio / SMILE_MOUTH_RATIO_MIN, lift / SMILE_CORNER_LIFT_MIN))

        mouth_ok = delta >= SMILE_MOUTH_DELTA_MIN and ratio >= SMILE_MOUTH_RATIO_MIN
        lift_ok = lift >= SMILE_CORNER_LIFT_MIN
        passed = mouth_ok or lift_ok

        detail = "Smile detected" if passed else "Show a clear, natural smile — lips wider or teeth visible."
        return LivenessStepResult(step=step, passed=passed, score=score, detail=detail)

    if step == "blink":
        eye = metrics.get("eye_ratio")
        base_eye = baseline.get("eye_ratio")
        if eye is None or base_eye is None:
            return LivenessStepResult(
                step=step,
                passed=False,
                score=0.0,
                detail="Could not detect your eyes. Look at the camera and blink once clearly.",
            )
        if metrics.get("source") == "opencv" and not metrics.get("eyes_detected"):
            return LivenessStepResult(
                step=step,
                passed=False,
                score=0.0,
                detail="Eyes not visible. Remove glasses if needed and blink clearly.",
            )

        ratio = float(eye / (base_eye + 1e-6))
        drop = float(base_eye - eye)
        score = min(
            1.0,
            max(
                (1.0 - ratio) / (1.0 - BLINK_EAR_RATIO_MAX + 1e-6),
                drop / BLINK_EAR_DELTA_MIN,
            ),
        )
        passed = drop >= BLINK_EAR_STRONG_DROP or (
            ratio <= BLINK_EAR_RATIO_MAX and drop >= BLINK_EAR_DELTA_MIN
        )
        detail = (
            "Blink detected"
            if passed
            else "Close your eyes fully, then tap Capture while they are still closed."
        )
        return LivenessStepResult(step=step, passed=passed, score=max(score, 0.0), detail=detail)

    if step == "head_left":
        delta = _yaw_delta(metrics, baseline)
        score = min(1.0, max(0.0, delta / HEAD_YAW_DELTA_MIN))
        passed = delta >= HEAD_YAW_DELTA_MIN
        return LivenessStepResult(
            step=step,
            passed=passed,
            score=score,
            detail="Head turned left" if passed else "Turn your head toward your left shoulder and hold.",
        )

    if step == "head_right":
        delta = _yaw_delta(metrics, baseline)
        score = min(1.0, max(0.0, -delta / HEAD_YAW_DELTA_MIN))
        passed = delta <= -HEAD_YAW_DELTA_MIN
        return LivenessStepResult(
            step=step,
            passed=passed,
            score=score,
            detail="Head turned right" if passed else "Turn your head toward your right shoulder and hold.",
        )

    return LivenessStepResult(step=step, passed=False, score=0.0, detail="Failed")


def aggregate_liveness_score(liveness_data: dict) -> float:
    if not liveness_data:
        return 0.0
    scores = []
    for step in LIVENESS_STEPS:
        entry = liveness_data.get(step)
        if entry and entry.get("passed"):
            scores.append(float(entry.get("score", 0)))
        else:
            scores.append(0.0)
    return float(sum(scores) / len(LIVENESS_STEPS)) if scores else 0.0


def all_liveness_steps_passed(liveness_data: dict) -> bool:
    return all(
        liveness_data.get(step, {}).get("passed") is True for step in LIVENESS_STEPS
    )
