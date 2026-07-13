# Generated migration for notification preferences and delivery logs

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="devicetoken",
            name="device_label",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name="devicetoken",
            name="last_used_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="NotificationPreference",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("push_enabled", models.BooleanField(default=True)),
                ("chat_enabled", models.BooleanField(default=True)),
                ("match_enabled", models.BooleanField(default=True)),
                ("likes_enabled", models.BooleanField(default=True)),
                ("marketing_enabled", models.BooleanField(default=False)),
                ("announcements_enabled", models.BooleanField(default=True)),
                ("verification_enabled", models.BooleanField(default=True)),
                ("payment_enabled", models.BooleanField(default=True)),
                ("sound_enabled", models.BooleanField(default=True)),
                ("vibration_enabled", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notification_preferences",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Notification preferences",
            },
        ),
        migrations.CreateModel(
            name="PushDeliveryLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("notification_type", models.CharField(max_length=64)),
                ("title", models.CharField(max_length=255)),
                ("body", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("sent", "Sent"),
                            ("failed", "Failed"),
                            ("skipped", "Skipped"),
                        ],
                        max_length=16,
                    ),
                ),
                ("devices_targeted", models.PositiveIntegerField(default=0)),
                ("devices_sent", models.PositiveIntegerField(default=0)),
                ("skip_reason", models.CharField(blank=True, max_length=255)),
                ("error_message", models.TextField(blank=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="push_delivery_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="devicetoken",
            index=models.Index(
                fields=["platform", "is_active"],
                name="notificatio_platfor_a8e2c1_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="pushdeliverylog",
            index=models.Index(
                fields=["user", "notification_type", "created_at"],
                name="notificatio_user_id_4f0b2a_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="pushdeliverylog",
            index=models.Index(
                fields=["status", "created_at"],
                name="notificatio_status_9c1d3e_idx",
            ),
        ),
    ]
