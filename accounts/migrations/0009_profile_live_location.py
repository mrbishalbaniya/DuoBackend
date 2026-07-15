from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0008_profile_discover_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="live_latitude",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="profile",
            name="live_longitude",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="profile",
            name="live_location_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
