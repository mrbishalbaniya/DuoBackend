"""Keep the verified badge honest when profile photos change.

The badge means "the person in these photos passed a live selfie check". If a
verified user adds a photo that wasn't there when they verified, that promise no
longer holds (verify with your real face, then swap in someone else's photos),
so the badge is removed and they're asked to verify again, as Tinder does.
Removing or reordering existing photos keeps the badge.
"""

from __future__ import annotations

from django.db.models.signals import pre_save
from django.dispatch import receiver

from accounts.models import Profile


def _photo_set(photo_url: str | None, photo_urls) -> set[str]:
    return {u for u in [photo_url, *(photo_urls or [])] if u}


@receiver(pre_save, sender=Profile, dispatch_uid="revoke_verified_badge_on_new_photo")
def revoke_verified_badge_on_new_photo(sender, instance: Profile, **kwargs):
    if not instance.pk or not instance.is_verified:
        return
    try:
        previous = Profile.objects.only("photo_url", "photo_urls").get(pk=instance.pk)
    except Profile.DoesNotExist:
        return

    before = _photo_set(previous.photo_url, previous.photo_urls)
    after = _photo_set(instance.photo_url, instance.photo_urls)
    if after - before:
        instance.is_verified = False
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "is_verified" not in update_fields:
            # save(update_fields=[...]) would otherwise skip the change.
            Profile.objects.filter(pk=instance.pk).update(is_verified=False)
