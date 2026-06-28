#!/usr/bin/env python
"""Set 3 profile photo URLs on every Profile (existing + future via seed scripts)."""
import json
import os
import sys

import django

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "duo_project.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from accounts.models import Profile  # noqa: E402

User = get_user_model()


def photo_urls_for_profile(profile):
    user = profile.user
    seed = user.username if user else f"profile-{profile.pk}"
    uid = user.id if user else profile.pk
    from duo_project.placeholder_photos import photo_urls_for_seed

    return photo_urls_for_seed(seed, uid)


def main():
    updated = 0
    for profile in Profile.objects.select_related("user").iterator():
        urls = photo_urls_for_profile(profile)
        profile.photo_urls = urls
        profile.photo_url = urls[0]
        profile.save(update_fields=["photo_urls", "photo_url", "updated_at"])
        updated += 1

    print(f"Updated {updated} profiles with 3 photo URLs each.")
    sample = Profile.objects.exclude(photo_urls=[]).first()
    if sample:
        print("Sample:", json.dumps(sample.photo_urls, indent=2))


if __name__ == "__main__":
    main()
