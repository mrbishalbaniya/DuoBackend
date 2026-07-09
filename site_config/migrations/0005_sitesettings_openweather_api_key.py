from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("site_config", "0004_sitesettings_email_brand_logo_url_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="openweather_api_key",
            field=models.CharField(
                blank=True,
                help_text="OpenWeather API key from openweathermap.org/api_keys. Leave blank when saving to keep the current value.",
                max_length=255,
            ),
        ),
    ]
