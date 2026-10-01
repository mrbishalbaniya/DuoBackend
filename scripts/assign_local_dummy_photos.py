"""Assign images from media/dummy_photos (copied from D:\8sem\IMAGES) to dummy users."""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "duo_project.settings")
django.setup()
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from accounts.models import Profile
from photo_verification.models import ProfilePhoto

DOMAINS = ("seed.duo.local", "example.com", "demo.com", "duo.local")
BASE = os.environ.get("DUMMY_PHOTO_BASE", "http://localhost:8000") + settings.MEDIA_URL + "dummy_photos/"
files = sorted(os.listdir(os.path.join(settings.MEDIA_ROOT, "dummy_photos")))
it = iter(files)
n = 0
with transaction.atomic():
    for p in Profile.objects.select_related("user").order_by("pk"):
        u = p.user
        if not u or u.is_staff or u.is_superuser or u.email.split("@")[-1] not in DOMAINS:
            continue
        urls = [BASE + next(it) for _ in range(3)]
        p.photo_url, p.photo_urls = urls[0], urls
        p.save(update_fields=["photo_url", "photo_urls"])
        ProfilePhoto.objects.filter(user=u).delete()
        now = timezone.now()
        for i, url in enumerate(urls):
            ProfilePhoto.objects.create(user=u, url=url, status="APPROVED", order=i, is_primary=i == 0,
                                        moderation_source="manual:seed_local_images", moderated_at=now)
        n += 1
print(f"Updated {n} dummy profiles")
