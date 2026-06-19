from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_discovery_filters"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="phone_country_code",
            field=models.CharField(blank=True, default="+977", max_length=8),
        ),
        migrations.AddField(
            model_name="profile",
            name="phone_number",
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
