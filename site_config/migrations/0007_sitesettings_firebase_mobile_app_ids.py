# Generated manually for DuoMobile push notification support.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("site_config", "0006_sitesettings_fcm_enabled_sitesettings_fcm_vapid_key_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="firebase_android_app_id",
            field=models.CharField(
                blank=True,
                help_text="Firebase Android app ID (1:...:android:...). Required for DuoMobile push.",
                max_length=128,
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="firebase_ios_app_id",
            field=models.CharField(
                blank=True,
                help_text="Firebase iOS app ID (1:...:ios:...). Required for DuoMobile push on iOS.",
                max_length=128,
            ),
        ),
    ]
