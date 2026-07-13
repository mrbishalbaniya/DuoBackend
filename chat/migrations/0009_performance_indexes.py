from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0008_security_system_messages"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="message",
            index=models.Index(
                fields=["conversation", "-timestamp"],
                name="msg_convo_ts_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="message",
            index=models.Index(
                fields=["conversation", "is_read", "sender"],
                name="msg_convo_read_sender_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="conversationpreference",
            index=models.Index(
                fields=["user", "is_archived"],
                name="convpref_user_arch_idx",
            ),
        ),
    ]
