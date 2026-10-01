import json
import re

from django.db import migrations


def _height_key(value):
    text = (value or "").strip()
    cm = re.search(r"(\d{2,3})\s*cm", text, re.I)
    if cm:
        return round(int(cm.group(1)) / 2.54)
    ft = re.search(r"(\d)\s*(?:'|ft|feet)\s*(\d{1,2})?", text, re.I)
    if ft:
        return int(ft.group(1)) * 12 + int(ft.group(2) or 0)
    return None


def forwards(apps, schema_editor):
    """Registration used to copy the member's own occupation and height into their
    partner preferences (and a "Professional Degree" default). Clear those copies
    so partner preferences only hold what the member chose on /preferences."""
    Profile = apps.get_model("accounts", "Profile")
    for profile in Profile.objects.all().iterator():
        changed = []
        own_job = (profile.occupation or "").strip().lower()
        pref_job = (profile.pref_occupation or "").strip().lower()
        if pref_job and (pref_job == own_job or pref_job == "professional degree"):
            profile.pref_occupation = ""
            changed.append("pref_occupation")

        try:
            extra = json.loads(profile.pref_values) if profile.pref_values else {}
        except (TypeError, ValueError):
            extra = {}
        own_height = _height_key(extra.get("height") if isinstance(extra, dict) else "")
        pref_height = _height_key(profile.pref_min_height)
        if profile.pref_min_height and (pref_height is None or pref_height == own_height):
            profile.pref_min_height = ""
            changed.append("pref_min_height")

        if changed:
            profile.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0013_generate_usernames_from_names")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
