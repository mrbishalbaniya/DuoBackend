"""Rewrite stored Devanagari place names in English.

    python manage.py englishify_places            # apply
    python manage.py englishify_places --dry-run  # only report
"""

import re

from django.core.management.base import BaseCommand

from accounts.english_places import DEVANAGARI, reverse_english, to_english
from accounts.models import Profile
from chat.models import Message
from notifications.models import PushDeliveryLog

# "Shared location: <address>\nhttps://www.google.com/maps/search/?api=1&query=LAT,LNG"
_SHARED = re.compile(r"^Shared location: (?P<addr>[^\n]*)(?P<rest>\n.*?query=(?P<lat>-?[\d.]+),(?P<lng>-?[\d.]+).*)$", re.S)


class Command(BaseCommand):
    help = (
        "Convert Devanagari place names to English: profile locations and the address in "
        "shared-location messages / push logs. Messages people typed are never changed."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def _fix_shared(self, text: str, cache: dict) -> str:
        match = _SHARED.match(text)
        if match:
            key = (match["lat"], match["lng"])
            if key not in cache:
                cache[key] = reverse_english(float(match["lat"]), float(match["lng"])) or to_english(match["addr"])
            return f"Shared location: {cache[key]}{match['rest']}"
        # Anything else is text people typed themselves: never rewrite it.
        return text

    def handle(self, *args, dry_run=False, **options):
        regex = DEVANAGARI.pattern
        changed = 0

        for profile in Profile.objects.filter(location__regex=regex) | Profile.objects.filter(pref_location__regex=regex):
            new_location = to_english(profile.location) or "Kathmandu, Nepal"
            new_pref = to_english(profile.pref_location)
            self.stdout.write(f"Profile {profile.pk}: {profile.location!r} -> {new_location!r}")
            if not dry_run:
                Profile.objects.filter(pk=profile.pk).update(location=new_location, pref_location=new_pref)
            changed += 1

        cache: dict = {}
        for message in Message.objects.filter(content__startswith="Shared location: ", content__regex=regex):
            new = self._fix_shared(message.content, cache)
            self.stdout.write(f"Message {message.pk}: -> {new.splitlines()[0]!r}")
            if not dry_run and new != message.content:
                Message.objects.filter(pk=message.pk).update(content=new)
            changed += 1

        for log in PushDeliveryLog.objects.filter(body__startswith="Shared location: ", body__regex=regex):
            new = self._fix_shared(log.body, cache)
            if not dry_run and new != log.body:
                PushDeliveryLog.objects.filter(pk=log.pk).update(body=new)
            changed += 1

        verb = "Would update" if dry_run else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} {changed} rows."))
