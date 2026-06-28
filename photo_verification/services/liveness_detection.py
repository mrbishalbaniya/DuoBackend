"""Liveness challenge validation (smile, blink, head turns)."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from photo_verification.constants import LIVENESS_STEPS
from photo_verification.ml.insightface_engine import _get_insightface_app

# MediaPipe Face Mesh landmark indices
_LEFT_EYE = (33, 160, 158, 133, 153, 144)
_RIGHT_EYE = (362, 385, 387, 263, 373, 380)
_MOUTH = (61, 291, 13, 14)  # corners + upper/lower lip center

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
        return 0.3
    v1 = np.linalg.norm(eye_pts[1] - eye_pts[5])
    v2 = np.linalg.norm(eye_pts[2] - eye_pts[4])
    h = np.linalg.norm(eye_pts[0] - eye_pts[3])
    return float((v1 + v2) / (2.0 * h + 1e-6))


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
    mouth = pts[list(_MOUTH)]

    left_ear = _eye_aspect_ratio(left_eye)
    right_ear = _eye_aspect_ratio(right_eye)
    eye_ratio = float((left_ear + right_ear) / 2.0)
    mouth_open = _mouth_aspect_ratio(mouth)

    nose = pts[1]
    left_cheek, right_cheek = pts[234], pts[454]
    face_mid_x = (left_cheek[0] + right_cheek[0]) / 2
    face_width = abs(right_cheek[0] - left_cheek[0]) + 1e-6
    yaw = float((nose[0] - face_mid_x) / face_width)

    return {
        "yaw": yaw,
        "mouth_open": mouth_open,
        "eye_ratio": eye_ratio,
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
        "mouth_open": float(np.linalg.norm(kps[3] - kps[4]) / (np.linalg.norm(kps[0] - kps[1]) + 1e-6)),
    }


def _analyze_with_opencv(rgb: np.ndarray) -> dict:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(80, 80))
    if len(faces) == 0:
        return {"yaw": 0.0, "mouth_open": 0.0, "eye_ratio": 0.3}

    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    roi = gray[y : y + h, x : x + w]
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
    eyes = eye_cascade.detectMultiScale(roi, 1.1, 8)
    eye_ratio = 0.15 if len(eyes) == 0 else 0.35
    mouth_region = roi[int(h * 0.6) :, :]
    mouth_var = float(np.std(mouth_region)) if mouth_region.size else 0.0
    cx_face = x + w / 2
    cx_img = rgb.shape[1] / 2
    yaw = float((cx_face - cx_img) / (rgb.shape[1] / 2 + 1e-6))
    return {"yaw": yaw, "mouth_open": mouth_var / 50.0, "eye_ratio": eye_ratio}


def _yaw_delta(metrics: dict, baseline: dict) -> float:
    """Positive = nose shifted right in frame (user turned to their left)."""
    return float(metrics.get("yaw", 0)) - float(baseline.get("yaw", 0))


def capture_baseline_metrics(rgb: np.ndarray) -> dict:
    return _analyze_with_mediapipe(rgb) or _analyze_with_insightface(rgb) or _analyze_with_opencv(rgb)


def validate_liveness_step(step: str, rgb: np.ndarray, baseline: dict | None = None) -> LivenessStepResult:
    if step not in LIVENESS_STEPS:
        return LivenessStepResult(step=step, passed=False, score=0.0, detail="Unknown step")

    metrics = _analyze_with_mediapipe(rgb) or _analyze_with_insightface(rgb) or _analyze_with_opencv(rgb)
    baseline = baseline or {}

    if step == "smile":
        mouth = metrics.get("mouth_open", 0)
        base_mouth = baseline.get("mouth_open", mouth * 0.7)
        score = min(1.0, mouth / (base_mouth + 0.08))
        passed = mouth > base_mouth + 0.05 or mouth > 0.35
        return LivenessStepResult(step=step, passed=passed, score=score, detail="Smile detected")

    if step == "blink":
        eye = metrics.get("eye_ratio", 0.3)
        base_eye = baseline.get("eye_ratio", 0.35)
        score = 1.0 - min(1.0, eye / (base_eye + 1e-6))
        passed = eye < base_eye * 0.55 or eye < 0.12
        return LivenessStepResult(step=step, passed=passed, score=max(score, 0.0), detail="Blink detected")

    if step == "head_left":
        delta = _yaw_delta(metrics, baseline)
        score = min(1.0, max(0.0, delta / 0.18))
        passed = delta > 0.06
        return LivenessStepResult(
            step=step,
            passed=passed,
            score=score,
            detail="Turn your head toward your left shoulder" if not passed else "Head turned left",
        )

    if step == "head_right":
        delta = _yaw_delta(metrics, baseline)
        score = min(1.0, max(0.0, -delta / 0.18))
        passed = delta < -0.06
        return LivenessStepResult(
            step=step,
            passed=passed,
            score=score,
            detail="Turn your head toward your right shoulder" if not passed else "Head turned right",
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
