from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_profile_photo_urls"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="pref_gender",
            field=models.CharField(
                choices=[
                    ("everyone", "Everyone"),
                    ("women", "Women"),
                    ("men", "Men"),
                ],
                default="everyone",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="pref_location",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="profile",
            name="pref_max_distance_km",
            field=models.IntegerField(default=50),
        ),
        migrations.AddField(
            model_name="profile",
            name="pref_relationship_goal",
            field=models.CharField(
                choices=[
                    ("everyone", "Everyone"),
                    ("serious", "Serious"),
                    ("casual", "Casual"),
                    ("dating", "Dating"),
                ],
                default="everyone",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="pref_verified_only",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="profile",
            name="relationship_goal",
            field=models.CharField(
                blank=True,
                choices=[
                    ("serious", "Serious"),
                    ("casual", "Casual"),
                    ("dating", "Dating"),
                ],
                default="",
                max_length=20,
            ),
        ),
    ]
