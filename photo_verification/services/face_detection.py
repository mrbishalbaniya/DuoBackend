"""Face detection via OpenCV (Haar cascade + optional DNN model)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

_DNN_NET = None
_MODEL_DIR = Path(__file__).resolve().parent.parent / "ml" / "models"


@dataclass(frozen=True)
class FaceDetectionResult:
    face_detected: bool
    face_count: int
    face_centered: bool
    face_boxes: list[tuple[int, int, int, int]]
    embedding: list[float]


def detect_faces(rgb: np.ndarray) -> FaceDetectionResult:
    boxes = _detect_with_dnn(rgb)
    if boxes is None:
        boxes = _detect_with_haar(rgb)

    count = len(boxes)
    centered = _is_face_centered(rgb.shape[1], rgb.shape[0], boxes)
    embedding = _face_embedding_from_boxes(rgb, boxes)

    return FaceDetectionResult(
        face_detected=count > 0,
        face_count=count,
        face_centered=centered,
        face_boxes=boxes,
        embedding=embedding,
    )


def _detect_with_dnn(rgb: np.ndarray) -> list[tuple[int, int, int, int]] | None:
    global _DNN_NET
    proto = _MODEL_DIR / "deploy.prototxt"
    weights = _MODEL_DIR / "res10_300x300_ssd_iter_140000.caffemodel"
    if not proto.is_file() or not weights.is_file():
        return None

    if _DNN_NET is None:
        _DNN_NET = cv2.dnn.readNetFromCaffe(str(proto), str(weights))

    h, w = rgb.shape[:2]
    blob = cv2.dnn.blobFromImage(rgb, 1.0, (300, 300), (104.0, 177.0, 123.0))
    _DNN_NET.setInput(blob)
    detections = _DNN_NET.forward()

    boxes: list[tuple[int, int, int, int]] = []
    for i in range(detections.shape[2]):
        confidence = float(detections[0, 0, i, 2])
        if confidence < 0.55:
            continue
        x1 = int(detections[0, 0, i, 3] * w)
        y1 = int(detections[0, 0, i, 4] * h)
        x2 = int(detections[0, 0, i, 5] * w)
        y2 = int(detections[0, 0, i, 6] * h)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 > x1 and y2 > y1:
            boxes.append((x1, y1, x2, y2))
    return boxes


def _detect_with_haar(rgb: np.ndarray) -> list[tuple[int, int, int, int]]:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(48, 48))
    return [(int(x), int(y), int(x + w), int(y + h)) for x, y, w, h in faces]


def _is_face_centered(
    width: int,
    height: int,
    boxes: list[tuple[int, int, int, int]],
) -> bool:
    if not boxes:
        return False

    from photo_verification.constants import FACE_CENTER_MAX_OFFSET

    cx_img, cy_img = width / 2, height / 2
    half_diag = ((width / 2) ** 2 + (height / 2) ** 2) ** 0.5

    primary = max(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    x1, y1, x2, y2 = primary
    cx_face = (x1 + x2) / 2
    cy_face = (y1 + y2) / 2
    dist = ((cx_face - cx_img) ** 2 + (cy_face - cy_img) ** 2) ** 0.5
    return dist / half_diag <= FACE_CENTER_MAX_OFFSET


def _face_embedding_from_boxes(
    rgb: np.ndarray,
    boxes: list[tuple[int, int, int, int]],
) -> list[float]:
    if not boxes:
        return []

    primary = max(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    x1, y1, x2, y2 = primary
    crop = rgb[y1:y2, x1:x2]
    if crop.size == 0:
        return []

    resized = cv2.resize(crop, (32, 32), interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(resized, cv2.COLOR_RGB2LAB)
    hist_l = cv2.calcHist([lab], [0], None, [16], [0, 256]).flatten()
    hist_a = cv2.calcHist([lab], [1], None, [8], [0, 256]).flatten()
    hist_b = cv2.calcHist([lab], [2], None, [8], [0, 256]).flatten()
    vec = np.concatenate([hist_l, hist_a, hist_b]).astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec.tolist()
