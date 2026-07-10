from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0006_messaging_enhancements"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversationpreference",
            name="is_pinned",
            field=models.BooleanField(default=False),
        ),
    ]
