"""Switch email delivery from Brevo to Nodemailer."""

from django.db import migrations, models


def migrate_brevo_to_nodemailer(apps, schema_editor):
    SiteSettings = apps.get_model("site_config", "SiteSettings")
    SiteSettings.objects.filter(email_delivery="brevo").update(email_delivery="nodemailer")
    SiteSettings.objects.filter(email_host="smtp-relay.brevo.com").update(email_host="")


class Migration(migrations.Migration):

    dependencies = [
        ("site_config", "0007_sitesettings_firebase_mobile_app_ids"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="email_relay_secret",
            field=models.CharField(
                blank=True,
                help_text="Shared secret for the Nodemailer relay. Leave blank when saving to keep the current value.",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="nodemailer_relay_url",
            field=models.URLField(
                blank=True,
                help_text="Optional relay URL (default: FRONTEND_URL/api/internal/email).",
                max_length=500,
            ),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="brevo_api_key",
            field=models.CharField(
                blank=True,
                help_text="Deprecated — no longer used. Leave blank.",
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="email_delivery",
            field=models.CharField(
                choices=[
                    ("nodemailer", "Nodemailer (recommended — HTTPS relay via frontend)"),
                    ("smtp", "SMTP direct (Django — use when relay is unavailable)"),
                    ("resend", "Resend API"),
                ],
                default="nodemailer",
                help_text="Nodemailer sends via the Duo frontend relay using the SMTP settings below.",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="email_host",
            field=models.CharField(
                blank=True,
                default="",
                help_text="SMTP host (Nodemailer: transport.host), e.g. smtp.gmail.com or smtp.sendgrid.net.",
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="email_host_password",
            field=models.CharField(
                blank=True,
                help_text="SMTP password or app password. Leave blank when saving to keep the current value.",
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="email_host_user",
            field=models.CharField(
                blank=True,
                help_text="SMTP username (Nodemailer: transport.auth.user).",
                max_length=255,
            ),
        ),
        migrations.RunPython(migrate_brevo_to_nodemailer, migrations.RunPython.noop),
    ]
