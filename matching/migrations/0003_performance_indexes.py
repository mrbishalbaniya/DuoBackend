from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("matching", "0002_profile_visit"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="swipe",
            index=models.Index(
                fields=["from_user", "-created_at"],
                name="swipe_from_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="swipe",
            index=models.Index(
                fields=["to_user", "action", "-created_at"],
                name="swipe_to_action_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="match",
            index=models.Index(fields=["-matched_at"], name="match_matched_at_idx"),
        ),
    ]
