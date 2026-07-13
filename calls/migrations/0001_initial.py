# Generated manually for calls app

import calls.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import calls.models as calls_models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("chat", "0009_performance_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="CallSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.CharField(db_index=True, default=calls_models._generate_public_id, max_length=16, unique=True)),
                ("call_type", models.CharField(choices=[("voice", "Voice"), ("video", "Video")], default="voice", max_length=8)),
                ("status", models.CharField(choices=[("initiating", "Initiating"), ("ringing", "Ringing"), ("active", "Active"), ("ended", "Ended"), ("missed", "Missed"), ("rejected", "Rejected"), ("busy", "Busy"), ("cancelled", "Cancelled"), ("failed", "Failed")], default="initiating", max_length=16)),
                ("end_reason", models.CharField(blank=True, default="", max_length=64)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("answered_at", models.DateTimeField(blank=True, null=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("ring_timeout_at", models.DateTimeField(blank=True, null=True)),
                ("duration_seconds", models.PositiveIntegerField(default=0)),
                ("quality_summary", models.JSONField(blank=True, default=dict)),
                ("callee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="calls_received", to=settings.AUTH_USER_MODEL)),
                ("caller", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="calls_initiated", to=settings.AUTH_USER_MODEL)),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="calls", to="chat.conversation")),
            ],
            options={
                "ordering": ["-started_at"],
            },
        ),
        migrations.AddIndex(
            model_name="callsession",
            index=models.Index(fields=["conversation", "-started_at"], name="call_convo_started_idx"),
        ),
        migrations.AddIndex(
            model_name="callsession",
            index=models.Index(fields=["caller", "status"], name="call_caller_status_idx"),
        ),
        migrations.AddIndex(
            model_name="callsession",
            index=models.Index(fields=["callee", "status"], name="call_callee_status_idx"),
        ),
        migrations.AddIndex(
            model_name="callsession",
            index=models.Index(fields=["status", "ring_timeout_at"], name="call_ring_timeout_idx"),
        ),
    ]
