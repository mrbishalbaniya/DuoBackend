"""Face matching between profile embeddings and selfie."""

from __future__ import annotations

from dataclasses import dataclass

from photo_verification.constants import SIMILARITY_REVIEW, SIMILARITY_VERIFIED
from photo_verification.ml.insightface_engine import cosine_similarity


@dataclass(frozen=True)
class FaceMatchResult:
    similarity_score: float
    best_profile_photo_url: str
    matched_embedding_id: int | None


def match_selfie_to_profile_embeddings(
    selfie_embedding: list[float],
    profile_embeddings: list,
) -> FaceMatchResult:
    best_score = 0.0
    best_url = ""
    best_id = None

    for record in profile_embeddings:
        vec = record.embedding_vector
        if not vec:
            continue
        score = cosine_similarity(selfie_embedding, vec)
        if score > best_score:
            best_score = score
            best_url = record.photo_url
            best_id = record.id

    return FaceMatchResult(
        similarity_score=best_score,
        best_profile_photo_url=best_url,
        matched_embedding_id=best_id,
    )


def similarity_tier(score: float) -> str:
    if score >= SIMILARITY_VERIFIED:
        return "verified"
    if score >= SIMILARITY_REVIEW:
        return "review"
    return "rejected"
