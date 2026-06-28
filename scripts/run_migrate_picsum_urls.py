#!/usr/bin/env python
"""Replace broken picsum.photos profile URLs with Unsplash placeholders."""
import json
import os
import sys

import django

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "duo_project.settings")
django.setup()

from accounts.models import Profile  # noqa: E402
from duo_project.placeholder_photos import photo_urls_for_seed  # noqa: E402


def main():
    updated = 0
    for profile in Profile.objects.select_related("user").iterator():
        urls = profile.photo_urls if isinstance(profile.photo_urls, list) else []
        has_picsum = "picsum.photos" in (profile.photo_url or "") or any(
            "picsum.photos" in (u or "") for u in urls
        )
        if not has_picsum:
            continue

        user = profile.user
        seed = user.username if user else f"profile-{profile.pk}"
        uid = user.id if user else profile.pk
        new_urls = photo_urls_for_seed(seed, uid)
        profile.photo_urls = new_urls
        profile.photo_url = new_urls[0]
        profile.save(update_fields=["photo_urls", "photo_url", "updated_at"])
        updated += 1

    print(f"Updated {updated} profiles (picsum -> Unsplash).")
    sample = Profile.objects.exclude(photo_url="").first()
    if sample:
        print("Sample:", json.dumps({"photo_url": sample.photo_url, "photo_urls": sample.photo_urls}, indent=2))


if __name__ == "__main__":
    main()
