"""Store face embeddings when profile photos are uploaded."""

from __future__ import annotations

import urllib.request

import numpy as np

from photo_verification.models import FaceEmbedding, PhotoAnalysis
from photo_verification.services.image_utils import load_image_from_bytes
from photo_verification.ml.insightface_engine import extract_face_embedding


def create_embedding_from_rgb(
    user,
    rgb: np.ndarray,
    *,
    photo_url: str,
    photo_analysis: PhotoAnalysis | None = None,
    quality_score: int = 0,
    is_primary: bool = False,
) -> FaceEmbedding | None:
    result = extract_face_embedding(rgb)
    if not result.embedding or result.face_count == 0:
        return None

    return FaceEmbedding.objects.create(
        user=user,
        photo_url=photo_url,
        photo_analysis=photo_analysis,
        embedding_vector=result.embedding,
        quality_score=quality_score,
        face_count=result.face_count,
        is_primary=is_primary,
    )


def create_embedding_from_upload(
    user,
    uploaded_file,
    *,
    photo_url: str,
    photo_analysis: PhotoAnalysis | None = None,
    quality_score: int = 0,
    is_primary: bool = False,
) -> FaceEmbedding | None:
    uploaded_file.seek(0)
    data = uploaded_file.read()
    uploaded_file.seek(0)
    loaded = load_image_from_bytes(data)
    return create_embedding_from_rgb(
        user,
        loaded.rgb,
        photo_url=photo_url,
        photo_analysis=photo_analysis,
        quality_score=quality_score,
        is_primary=is_primary,
    )


def sync_embeddings_from_profile(user) -> int:
    """Backfill embeddings from profile photo URLs when missing."""
    profile = user.profile
    urls = []
    if profile.photo_url:
        urls.append((profile.photo_url, True))
    for url in profile.photo_urls or []:
        if url and url not in [u for u, _ in urls]:
            urls.append((url, False))

    created = 0
    for url, is_primary in urls:
        exists = FaceEmbedding.objects.filter(user=user, photo_url=url).exists()
        if exists:
            continue
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = resp.read()
            loaded = load_image_from_bytes(data)
            if create_embedding_from_rgb(user, loaded.rgb, photo_url=url, is_primary=is_primary):
                created += 1
        except Exception:
            continue
    return created


def get_user_profile_embeddings(user):
    return list(
        FaceEmbedding.objects.filter(user=user).exclude(embedding_vector=[]).order_by("-is_primary", "-created_at")
    )
