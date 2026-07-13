from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0002_notification_preferences_and_delivery_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationpreference",
            name="calls_enabled",
            field=models.BooleanField(default=True),
        ),
    ]
