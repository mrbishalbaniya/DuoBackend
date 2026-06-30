# Generated manually for Resend email support on Render free tier.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("site_config", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="email_delivery",
            field=models.CharField(
                choices=[
                    ("smtp", "SMTP (local dev / paid Render)"),
                    ("resend", "Resend API (required on Render free tier)"),
                ],
                default="resend",
                help_text=(
                    "Render free tier blocks SMTP ports 587/465. Use Resend on production "
                    "or upgrade Render to a paid plan for Gmail SMTP."
                ),
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="resend_api_key",
            field=models.CharField(
                blank=True,
                help_text="Resend API key (re_...). Leave blank when saving to keep the current value.",
                max_length=255,
            ),
        ),
    ]
