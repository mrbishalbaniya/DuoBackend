# Generated manually for security score / severity / geo fields.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("security", "0002_rename_security_ba_user_id_3c8e2a_idx_security_ba_user_id_b3650f_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="userdevice",
            name="country",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="userdevice",
            name="city",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="loginhistory",
            name="country",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="loginhistory",
            name="city",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="loginhistory",
            name="event_type",
            field=models.CharField(
                blank=True,
                default="login",
                help_text="login | logout | password_changed | 2fa_enabled | ...",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="securityevent",
            name="severity",
            field=models.CharField(
                choices=[
                    ("info", "Info"),
                    ("warning", "Warning"),
                    ("critical", "Critical"),
                ],
                db_index=True,
                default="info",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="twofactorsettings",
            name="totp_secret",
            field=models.CharField(
                blank=True,
                help_text="Fernet-encrypted TOTP seed (enc:…).",
                max_length=256,
            ),
        ),
    ]
