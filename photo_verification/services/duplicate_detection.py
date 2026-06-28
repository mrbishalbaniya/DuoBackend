"""Compare uploads against the user's history and global perceptual hashes."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from photo_verification.constants import DUPLICATE_FLAG_THRESHOLD


@dataclass(frozen=True)
class DuplicateDetectionResult:
    duplicate_probability: float
    matched_analysis_id: int | None


def hash_similarity(bits_a: np.ndarray, bits_b: np.ndarray) -> float:
    if bits_a.size == 0 or bits_b.size == 0 or bits_a.size != bits_b.size:
        return 0.0
    agreement = 1.0 - np.mean(bits_a != bits_b)
    return float(np.clip(agreement, 0.0, 1.0))


def embedding_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    a = np.asarray(vec_a, dtype=np.float32)
    b = np.asarray(vec_b, dtype=np.float32)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.clip(np.dot(a, b) / denom, 0.0, 1.0))


def detect_duplicate(
    *,
    hash_bits: np.ndarray,
    face_embedding: list[float],
    user_id: int,
    exclude_id: int | None = None,
) -> DuplicateDetectionResult:
    from photo_verification.models import PhotoAnalysis

    qs = PhotoAnalysis.objects.filter(user_id=user_id).exclude(image_hash="")
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)

    best_prob = 0.0
    best_id: int | None = None

    for record in qs.only("id", "embedding", "image_hash")[:50]:
        if not record.image_hash:
            continue
        try:
            stored_bits = _hex_to_bits(record.image_hash, hash_bits.size)
            hash_sim = hash_similarity(hash_bits, stored_bits)
            emb_sim = embedding_similarity(face_embedding, record.embedding or [])
            combined = 0.7 * hash_sim + 0.3 * emb_sim if emb_sim > 0 else hash_sim
            if combined > best_prob:
                best_prob = combined
                best_id = record.id
        except (ValueError, TypeError):
            continue

    # Cross-user duplicate scan (limited sample for performance)
    global_qs = (
        PhotoAnalysis.objects.exclude(user_id=user_id)
        .exclude(image_hash="")
        .order_by("-created_at")[:200]
    )
    for record in global_qs.only("id", "image_hash"):
        try:
            stored_bits = _hex_to_bits(record.image_hash, hash_bits.size)
            hash_sim = hash_similarity(hash_bits, stored_bits)
            if hash_sim > best_prob:
                best_prob = hash_sim
                best_id = record.id
        except ValueError:
            continue

    return DuplicateDetectionResult(
        duplicate_probability=best_prob,
        matched_analysis_id=best_id if best_prob >= DUPLICATE_FLAG_THRESHOLD else None,
    )


def _hex_to_bits(hex_str: str, expected_len: int) -> np.ndarray:
    as_int = int(hex_str, 16)
    bits = np.array([(as_int >> i) & 1 for i in range(expected_len - 1, -1, -1)], dtype=np.float32)
    if bits.size < expected_len:
        bits = np.pad(bits, (expected_len - bits.size, 0))
    return bits[:expected_len]
