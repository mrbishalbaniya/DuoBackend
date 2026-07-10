from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_profile_phone"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="location_ghost_mode",
            field=models.BooleanField(
                default=False,
                help_text="When enabled, friends cannot see your location on the map.",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="location_visibility",
            field=models.CharField(
                choices=[
                    ("friends", "My friends"),
                    ("friends_except", "My friends, except…"),
                    ("only_these", "Only these friends"),
                ],
                default="friends",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="location_visibility_friends",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="User IDs for friends_except / only_these modes.",
            ),
        ),
    ]
