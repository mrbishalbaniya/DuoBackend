from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("site_config", "0002_email_resend"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="brevo_api_key",
            field=models.CharField(
                blank=True,
                help_text="Brevo API key (xkeysib-...). Leave blank when saving to keep the current value.",
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="email_delivery",
            field=models.CharField(
                choices=[
                    ("brevo", "Brevo API (recommended on Render free — works with Gmail sender)"),
                    ("resend", "Resend API (requires verified domain)"),
                    ("smtp", "SMTP (local dev / paid Render only)"),
                ],
                default="brevo",
                help_text="Render free tier blocks SMTP ports 587/465. Use Brevo or Resend on production.",
                max_length=16,
            ),
        ),
    ]
