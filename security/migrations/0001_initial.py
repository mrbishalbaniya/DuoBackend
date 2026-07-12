# Generated manually for security app

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TwoFactorSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(default=False)),
                ("method", models.CharField(blank=True, choices=[("email", "Email OTP"), ("totp", "Authenticator App"), ("sms", "SMS OTP")], max_length=16)),
                ("totp_secret", models.CharField(blank=True, max_length=128)),
                ("remember_device_days", models.PositiveSmallIntegerField(default=30)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="two_factor_settings", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name_plural": "Two-factor settings"},
        ),
        migrations.CreateModel(
            name="UserDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("device_id", models.CharField(db_index=True, max_length=128)),
                ("device_name", models.CharField(blank=True, max_length=128)),
                ("model", models.CharField(blank=True, max_length=128)),
                ("platform", models.CharField(choices=[("android", "Android"), ("ios", "iOS"), ("web", "Web"), ("unknown", "Unknown")], default="unknown", max_length=16)),
                ("os_version", models.CharField(blank=True, max_length=64)),
                ("app_version", models.CharField(blank=True, max_length=32)),
                ("browser", models.CharField(blank=True, max_length=64)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("location", models.CharField(blank=True, max_length=128)),
                ("push_token", models.CharField(blank=True, max_length=512)),
                ("is_trusted", models.BooleanField(default=False)),
                ("trusted_until", models.DateTimeField(blank=True, null=True)),
                ("last_active", models.DateTimeField(default=django.utils.timezone.now)),
                ("login_time", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="devices", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-last_active"]},
        ),
        migrations.CreateModel(
            name="UserSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("refresh_jti", models.CharField(db_index=True, max_length=64, unique=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, max_length=512)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_active", models.DateTimeField(default=django.utils.timezone.now)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("device", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sessions", to="security.userdevice")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sessions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-last_active"]},
        ),
        migrations.CreateModel(
            name="SecurityEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("new_login", "New login"), ("new_device", "New device"), ("password_changed", "Password changed"), ("two_fa_enabled", "2FA enabled"), ("two_fa_disabled", "2FA disabled"), ("biometric_enabled", "Biometric enabled"), ("biometric_disabled", "Biometric disabled"), ("device_logout", "Device logged out"), ("logout_all", "Logged out all devices"), ("device_trusted", "Device trusted"), ("device_untrusted", "Device untrusted"), ("suspicious_login", "Suspicious login"), ("failed_login", "Failed login"), ("backup_codes_regenerated", "Backup codes regenerated")], max_length=32)),
                ("title", models.CharField(max_length=128)),
                ("message", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="security_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="LoginHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("success", models.BooleanField(default=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("location", models.CharField(blank=True, max_length=128)),
                ("device_name", models.CharField(blank=True, max_length=128)),
                ("browser", models.CharField(blank=True, max_length=64)),
                ("os_name", models.CharField(blank=True, max_length=64)),
                ("user_agent", models.CharField(blank=True, max_length=512)),
                ("failure_reason", models.CharField(blank=True, max_length=128)),
                ("is_current", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("device", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="login_entries", to="security.userdevice")),
                ("session", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="login_entries", to="security.usersession")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="login_history", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name_plural": "Login history", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="BiometricCredential",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_hash", models.CharField(db_index=True, max_length=64, unique=True)),
                ("is_enabled", models.BooleanField(default=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="biometric_credentials", to="security.userdevice")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="biometric_credentials", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="BackupCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code_hash", models.CharField(db_index=True, max_length=64)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="backup_codes", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddIndex(
            model_name="userdevice",
            index=models.Index(fields=["user", "last_active"], name="security_us_user_id_6f0f0d_idx"),
        ),
        migrations.AddIndex(
            model_name="userdevice",
            index=models.Index(fields=["user", "is_trusted"], name="security_us_user_id_8a2c4e_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="userdevice",
            unique_together={("user", "device_id")},
        ),
        migrations.AddIndex(
            model_name="usersession",
            index=models.Index(fields=["user", "is_active"], name="security_us_user_id_1b3d2a_idx"),
        ),
        migrations.AddIndex(
            model_name="usersession",
            index=models.Index(fields=["refresh_jti"], name="security_us_refresh_7c5e1f_idx"),
        ),
        migrations.AddIndex(
            model_name="securityevent",
            index=models.Index(fields=["user", "-created_at"], name="security_se_user_id_4d8a2b_idx"),
        ),
        migrations.AddIndex(
            model_name="securityevent",
            index=models.Index(fields=["user", "is_read"], name="security_se_user_id_9f1c3e_idx"),
        ),
        migrations.AddIndex(
            model_name="loginhistory",
            index=models.Index(fields=["user", "-created_at"], name="security_lo_user_id_2e7b4c_idx"),
        ),
        migrations.AddIndex(
            model_name="biometriccredential",
            index=models.Index(fields=["user", "is_enabled"], name="security_bi_user_id_5a9d1f_idx"),
        ),
        migrations.AddIndex(
            model_name="backupcode",
            index=models.Index(fields=["user", "used_at"], name="security_ba_user_id_3c8e2a_idx"),
        ),
    ]
