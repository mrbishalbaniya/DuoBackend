"""Create ProfilePhoto tracking rows for photos that predate the moderation
pipeline (seeded/demo profiles, any photo set directly via admin/DB tooling,
or anything uploaded before this system existed).

These photos were never run through content-safety moderation. This command
does NOT hide or delete them — a sudden mass takedown of existing users'
photos from a brand-new local model is a bigger decision than a migration
script should make unilaterally, and false positives at scale would be its
own incident. It creates them as MANUAL_REVIEW so admins have visibility and
tooling to review the backlog deliberately (see the project plan's
Assumptions section).

Usage:
    python manage.py remoderate_legacy_photos [--dry-run]
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Profile
from photo_verification.constants import ModerationStatus
from photo_verification.models import ProfilePhoto


class Command(BaseCommand):
    help = "Create MANUAL_REVIEW ProfilePhoto rows for photos that predate the moderation pipeline."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be created without writing anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        User = get_user_model()

        tracked_urls_by_user: dict[int, set[str]] = {}
        for user_id, url in ProfilePhoto.objects.values_list("user_id", "url"):
            tracked_urls_by_user.setdefault(user_id, set()).add(url)

        created = 0
        affected_users = 0

        for profile in Profile.objects.select_related("user").iterator():
            urls: list[str] = []
            if profile.photo_url:
                urls.append(profile.photo_url)
            urls.extend(u for u in (profile.photo_urls or []) if u)

            tracked = tracked_urls_by_user.get(profile.user_id, set())
            untracked = [u for u in urls if u and u not in tracked]
            if not untracked:
                continue

            affected_users += 1
            self.stdout.write(f"user={profile.user_id} ({profile.user.username}): {len(untracked)} legacy photo(s)")

            if dry_run:
                created += len(untracked)
                continue

            existing_count = ProfilePhoto.objects.filter(user_id=profile.user_id).count()
            for offset, url in enumerate(untracked):
                ProfilePhoto.objects.create(
                    user_id=profile.user_id,
                    url=url,
                    status=ModerationStatus.MANUAL_REVIEW,
                    rejection_reason="",
                    rejection_category="",
                    moderation_source="legacy_migration",
                    moderated_at=timezone.now(),
                    order=existing_count + offset,
                    is_primary=(url == profile.photo_url),
                )
                created += 1

        verb = "Would create" if dry_run else "Created"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {created} ProfilePhoto row(s) (MANUAL_REVIEW) across {affected_users} user(s)."
            )
        )
