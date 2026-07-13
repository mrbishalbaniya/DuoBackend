"""Add WebRTC STUN/TURN settings to Integration settings."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("site_config", "0008_nodemailer_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="webrtc_stun_urls",
            field=models.TextField(
                blank=True,
                help_text=(
                    "Comma-separated STUN server URLs for WebRTC ICE. "
                    "Google defaults: stun:stun.l.google.com:19302,stun:stun1.l.google.com:19302"
                ),
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="webrtc_turn_credential",
            field=models.CharField(
                blank=True,
                help_text="Static TURN password. Leave blank when saving to keep the current value.",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="webrtc_turn_secret",
            field=models.CharField(
                blank=True,
                help_text=(
                    "coturn shared secret for time-limited credentials. "
                    "Leave blank when saving to keep the current value."
                ),
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="webrtc_turn_ttl",
            field=models.PositiveIntegerField(
                blank=True,
                default=86400,
                help_text="TURN credential lifetime in seconds when using shared secret (default 86400).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="webrtc_turn_url",
            field=models.CharField(
                blank=True,
                help_text="Optional TURN relay URL (turn: or turns:). Leave blank to use STUN only.",
                max_length=500,
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="webrtc_turn_username",
            field=models.CharField(
                blank=True,
                help_text="Static TURN username. Ignored when TURN shared secret is set.",
                max_length=255,
            ),
        ),
    ]
