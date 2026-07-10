# Generated manually for Conversation.public_id

from django.db import migrations, models
import secrets


def generate_public_id():
    return str(secrets.randbelow(9_000_000_000) + 1_000_000_000)


def backfill_public_ids(apps, schema_editor):
    Conversation = apps.get_model("chat", "Conversation")
    used = set(
        Conversation.objects.exclude(public_id="")
        .exclude(public_id__isnull=True)
        .values_list("public_id", flat=True)
    )
    for convo in Conversation.objects.all().iterator():
        if convo.public_id:
            continue
        for _ in range(40):
            candidate = generate_public_id()
            if candidate not in used:
                used.add(candidate)
                Conversation.objects.filter(pk=convo.pk).update(public_id=candidate)
                break
        else:
            raise RuntimeError(f"Could not allocate public_id for conversation {convo.pk}")


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0004_conversation_actions"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="public_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                editable=False,
                max_length=10,
            ),
        ),
        migrations.RunPython(backfill_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="conversation",
            name="public_id",
            field=models.CharField(
                db_index=True,
                editable=False,
                max_length=10,
                unique=True,
            ),
        ),
    ]
