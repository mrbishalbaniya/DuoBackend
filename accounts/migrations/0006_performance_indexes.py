from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_location_privacy"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="profile",
            index=models.Index(
                fields=["is_onboarded", "gender", "age"],
                name="profile_discover_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="profile",
            index=models.Index(fields=["is_verified"], name="profile_verified_idx"),
        ),
        migrations.AddIndex(
            model_name="profile",
            index=models.Index(fields=["-updated_at"], name="profile_updated_idx"),
        ),
        migrations.AddIndex(
            model_name="profile",
            index=models.Index(fields=["gender"], name="profile_gender_idx"),
        ),
    ]
