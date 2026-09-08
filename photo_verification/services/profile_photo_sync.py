"""Keeps accounts.Profile.photo_url/photo_urls consistent with ProfilePhoto
moderation state. Call after any ProfilePhoto status change or deletion.

Only ever removes/replaces URLs that belong to a ProfilePhoto row for this
user — never touches unrelated profile fields. This is what makes "if the
primary photo is rejected or deleted, automatically promote another approved
photo" a real-time guarantee rather than something that only happens on the
user's next manual save.
"""

from __future__ import annotations

from photo_verification.constants import ModerationStatus


def sync_profile_photos(user) -> None:
    from accounts.models import Profile
    from photo_verification.models import ProfilePhoto

    try:
        profile = user.profile
    except Profile.DoesNotExist:
        return

    all_photos = {p.url: p for p in ProfilePhoto.objects.filter(user=user)}
    approved = list(
        ProfilePhoto.objects.filter(user=user, status=ModerationStatus.APPROVED).order_by(
            "order", "uploaded_at"
        )
    )
    approved_urls = {p.url for p in approved}

    changed = False
    current_gallery = list(profile.photo_urls or [])

    def _still_valid(url: str) -> bool:
        # Not one of ours (e.g. legacy/manually-set) -> leave untouched.
        # Ours -> only keep while APPROVED.
        return url not in all_photos or url in approved_urls

    if profile.photo_url and not _still_valid(profile.photo_url):
        profile.photo_url = ""
        changed = True

    new_gallery = [u for u in current_gallery if _still_valid(u)]
    if new_gallery != current_gallery:
        profile.photo_urls = new_gallery
        changed = True

    if not profile.photo_url and approved:
        promoted = approved[0]
        profile.photo_url = promoted.url
        if promoted.url in (profile.photo_urls or []):
            profile.photo_urls = [u for u in profile.photo_urls if u != promoted.url]
        changed = True

    if changed:
        profile.save(update_fields=["photo_url", "photo_urls"])

    ProfilePhoto.objects.filter(user=user, is_primary=True).exclude(url=profile.photo_url).update(
        is_primary=False
    )
    if profile.photo_url in all_photos:
        ProfilePhoto.objects.filter(user=user, url=profile.photo_url).update(is_primary=True)
