"""InsightFace embedding extraction with OpenCV fallback."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from photo_verification.services.face_detection import detect_faces


@dataclass(frozen=True)
class FaceEmbeddingResult:
    embedding: list[float]
    face_count: int
    bbox: tuple[int, int, int, int] | None
    detector: str  # "insightface" | "opencv"


_insightface_app = None
_insightface_checked = False


def _get_insightface_app():
    global _insightface_app, _insightface_checked
    if _insightface_checked:
        return _insightface_app

    _insightface_checked = True
    try:
        from insightface.app import FaceAnalysis

        app = FaceAnalysis(
            name="buffalo_l",
            providers=["CPUExecutionProvider"],
        )
        app.prepare(ctx_id=0, det_size=(640, 640))
        _insightface_app = app
    except Exception:
        _insightface_app = None
    return _insightface_app


def extract_face_embedding(rgb: np.ndarray) -> FaceEmbeddingResult:
    app = _get_insightface_app()
    if app is not None:
        faces = app.get(rgb)
        if faces:
            primary = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
            vec = primary.embedding.astype(np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            bbox = tuple(int(x) for x in primary.bbox)
            return FaceEmbeddingResult(
                embedding=vec.tolist(),
                face_count=len(faces),
                bbox=bbox,
                detector="insightface",
            )

    detection = detect_faces(rgb)
    if not detection.embedding:
        return FaceEmbeddingResult(
            embedding=[],
            face_count=detection.face_count,
            bbox=detection.face_boxes[0] if detection.face_boxes else None,
            detector="opencv",
        )

    vec = np.asarray(detection.embedding, dtype=np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = (vec / norm).tolist()
    else:
        vec = detection.embedding

    return FaceEmbeddingResult(
        embedding=vec,
        face_count=detection.face_count,
        bbox=detection.face_boxes[0] if detection.face_boxes else None,
        detector="opencv",
    )


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.clip(np.dot(va, vb) / denom, 0.0, 1.0))
