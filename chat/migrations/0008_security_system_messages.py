from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0007_conversation_preference_is_pinned"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversationpreference",
            name="notify_screenshots",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="conversationpreference",
            name="secure_chat",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="message",
            name="event_code",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AlterField(
            model_name="message",
            name="message_type",
            field=models.CharField(
                choices=[
                    ("text", "Text"),
                    ("image", "Image"),
                    ("voice", "Voice"),
                    ("system", "System"),
                ],
                default="text",
                max_length=10,
            ),
        ),
    ]
