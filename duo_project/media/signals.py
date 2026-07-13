"""Automatic cleanup when media URLs are replaced or removed."""

from __future__ import annotations

import logging

from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from accounts.models import Profile
from chat.models import Message
from photo_verification.models import PhotoAnalysis, UserVerification

from .cleanup import delete_media_at_url
from .config import media_storage_backend

logger = logging.getLogger("duo.media")


def _delete_media_url(url: str | None) -> None:
    if not url:
        return
    if media_storage_backend() == "r2":
        delete_media_at_url(url)
        return
    from duo_project.cloudinary_media.cleanup import delete_cloudinary_url

    delete_cloudinary_url(url)


def _connect_media_cleanup_signals() -> None:
    """Receivers register on import via @receiver decorators."""
    logger.debug("media_cleanup_signals_connected")


@receiver(pre_save, sender=Profile)
def cleanup_old_profile_photo(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old = Profile.objects.filter(pk=instance.pk).values("photo_url", "photo_urls").first()
        if not old:
            return
        new_urls = {instance.photo_url, *(instance.photo_urls or [])}
        old_urls = {old.get("photo_url"), *(old.get("photo_urls") or [])}
        for url in old_urls:
            if url and url not in new_urls:
                _delete_media_url(url)
    except Exception:
        pass


@receiver(post_delete, sender=Message)
def cleanup_message_media(sender, instance, **kwargs):
    if instance.image_url:
        _delete_media_url(instance.image_url)


@receiver(post_delete, sender=PhotoAnalysis)
def cleanup_photo_analysis(sender, instance, **kwargs):
    _delete_media_url(instance.image_url)


@receiver(pre_save, sender=UserVerification)
def cleanup_verification_selfie(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old_url = (
            UserVerification.objects.filter(pk=instance.pk)
            .values_list("selfie_photo_url", flat=True)
            .first()
        )
        if old_url and old_url != instance.selfie_photo_url:
            _delete_media_url(old_url)
    except Exception:
        pass
