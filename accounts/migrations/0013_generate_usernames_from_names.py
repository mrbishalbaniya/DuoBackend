import re
import secrets
import unicodedata

from django.conf import settings
from django.db import migrations


def _slug(text):
    ascii_text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return ".".join(re.findall(r"[a-z0-9]+", ascii_text.lower()))[:20].strip(".")


def forwards(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(app_label, model_name)
    Profile = apps.get_model("accounts", "Profile")
    names = dict(Profile.objects.values_list("user_id", "full_name"))
    taken = {u.lower() for u in User.objects.values_list("username", flat=True)}

    users = User.objects.filter(username__contains="@", is_staff=False, is_superuser=False)
    for user in users.iterator():
        name = names.get(user.id) or f"{user.first_name} {user.last_name}".strip()
        base = _slug(name) or _slug((user.email or user.username).split("@")[0].replace(".", " "))
        if len(base) < 2:
            base = "duo.user"
        candidate = f"{base}{secrets.randbelow(9000) + 1000}"
        while candidate in taken:
            candidate = f"{base}{secrets.randbelow(9000) + 1000}"
        taken.discard(user.username.lower())
        taken.add(candidate)
        user.username = candidate
        user.save(update_fields=["username"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0012_discovery_expand_prefs"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
