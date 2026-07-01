"""Record and query profile visits."""

from __future__ import annotations

from django.contrib.auth.models import User

from matching.models import ProfileVisit


def record_profile_visit(viewer: User, viewed_user: User) -> None:
    if not viewer or not viewer.is_authenticated:
        return
    if viewer.id == viewed_user.id:
        return

    ProfileVisit.objects.update_or_create(
        viewer=viewer,
        viewed_user=viewed_user,
        defaults={},
    )
