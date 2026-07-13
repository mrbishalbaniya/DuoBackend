"""Photo verification and embedding background tasks."""

from __future__ import annotations

import logging
import urllib.request

from celery import shared_task

from duo_project.tasks import NETWORK_RETRY_KWARGS

logger = logging.getLogger("duo.celery")


@shared_task(
    name="duo_project.tasks.verification.create_photo_embedding",
    bind=True,
    **NETWORK_RETRY_KWARGS,
)
def create_photo_embedding_task(
    self,
    user_id: int,
    photo_url: str,
    photo_analysis_id: int | None = None,
    quality_score: int = 0,
    is_primary: bool = False,
) -> bool:
    from django.contrib.auth import get_user_model

    from photo_verification.models import PhotoAnalysis
    from photo_verification.services.embedding_pipeline import create_embedding_from_rgb
    from photo_verification.services.image_utils import load_image_from_bytes

    User = get_user_model()
    user = User.objects.filter(pk=user_id).first()
    if not user or not photo_url:
        return False

    analysis = None
    if photo_analysis_id:
        analysis = PhotoAnalysis.objects.filter(pk=photo_analysis_id, user=user).first()

    try:
        with urllib.request.urlopen(photo_url, timeout=30) as resp:
            data = resp.read()
        loaded = load_image_from_bytes(data)
        embedding = create_embedding_from_rgb(
            user,
            loaded.rgb,
            photo_url=photo_url,
            photo_analysis=analysis,
            quality_score=quality_score,
            is_primary=is_primary,
        )
        return embedding is not None
    except Exception as exc:
        logger.warning(
            "create_photo_embedding_failed user_id=%s url=%s error=%s",
            user_id,
            photo_url[:80],
            exc,
        )
        raise
