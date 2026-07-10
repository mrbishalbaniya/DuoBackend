from django.db import migrations, models
import django.db.models.deletion


def backfill_last_message_at(apps, schema_editor):
    Conversation = apps.get_model("chat", "Conversation")
    Message = apps.get_model("chat", "Message")
    for convo in Conversation.objects.all():
        latest = (
            Message.objects.filter(conversation_id=convo.id)
            .order_by("-timestamp")
            .values_list("timestamp", flat=True)
            .first()
        )
        if latest:
            convo.last_message_at = latest
            convo.save(update_fields=["last_message_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0005_conversation_public_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="last_message_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="conversationpreference",
            name="is_archived",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="conversationpreference",
            name="is_muted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="message",
            name="delivered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="message",
            name="read_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="message",
            name="edited_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="message",
            name="message_type",
            field=models.CharField(
                choices=[("text", "Text"), ("image", "Image"), ("voice", "Voice")],
                default="text",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="message",
            name="reply_to",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="replies",
                to="chat.message",
            ),
        ),
        migrations.RunPython(backfill_last_message_at, migrations.RunPython.noop),
    ]
