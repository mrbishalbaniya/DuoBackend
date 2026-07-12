import hashlib
import secrets
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


class TwoFactorMethod(models.TextChoices):
    EMAIL = "email", "Email OTP"
    TOTP = "totp", "Authenticator App"
    SMS = "sms", "SMS OTP"


class SecurityEventType(models.TextChoices):
    NEW_LOGIN = "new_login", "New login"
    NEW_DEVICE = "new_device", "New device"
    PASSWORD_CHANGED = "password_changed", "Password changed"
    TWO_FA_ENABLED = "two_fa_enabled", "2FA enabled"
    TWO_FA_DISABLED = "two_fa_disabled", "2FA disabled"
    BIOMETRIC_ENABLED = "biometric_enabled", "Biometric enabled"
    BIOMETRIC_DISABLED = "biometric_disabled", "Biometric disabled"
    DEVICE_LOGOUT = "device_logout", "Device logged out"
    LOGOUT_ALL = "logout_all", "Logged out all devices"
    DEVICE_TRUSTED = "device_trusted", "Device trusted"
    DEVICE_UNTRUSTED = "device_untrusted", "Device untrusted"
    SUSPICIOUS_LOGIN = "suspicious_login", "Suspicious login"
    FAILED_LOGIN = "failed_login", "Failed login"
    BACKUP_CODES_REGENERATED = "backup_codes_regenerated", "Backup codes regenerated"


class DevicePlatform(models.TextChoices):
    ANDROID = "android", "Android"
    IOS = "ios", "iOS"
    WEB = "web", "Web"
    UNKNOWN = "unknown", "Unknown"


class TwoFactorSettings(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="two_factor_settings",
    )
    is_enabled = models.BooleanField(default=False)
    method = models.CharField(
        max_length=16,
        choices=TwoFactorMethod.choices,
        blank=True,
    )
    totp_secret = models.CharField(max_length=128, blank=True)
    remember_device_days = models.PositiveSmallIntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Two-factor settings"

    def __str__(self):
        return f"2FA for {self.user_id} ({'on' if self.is_enabled else 'off'})"


class BackupCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="backup_codes")
    code_hash = models.CharField(max_length=64, db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "used_at"])]

    @staticmethod
    def hash_code(code: str) -> str:
        return hashlib.sha256(code.strip().upper().encode()).hexdigest()

    @classmethod
    def generate_codes(cls, user, count: int = 8) -> list[str]:
        cls.objects.filter(user=user, used_at__isnull=True).delete()
        plain_codes: list[str] = []
        for _ in range(count):
            plain = f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"
            plain_codes.append(plain)
            cls.objects.create(user=user, code_hash=cls.hash_code(plain))
        return plain_codes


class UserDevice(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="devices")
    device_id = models.CharField(max_length=128, db_index=True)
    device_name = models.CharField(max_length=128, blank=True)
    model = models.CharField(max_length=128, blank=True)
    platform = models.CharField(
        max_length=16,
        choices=DevicePlatform.choices,
        default=DevicePlatform.UNKNOWN,
    )
    os_version = models.CharField(max_length=64, blank=True)
    app_version = models.CharField(max_length=32, blank=True)
    browser = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    location = models.CharField(max_length=128, blank=True)
    push_token = models.CharField(max_length=512, blank=True)
    is_trusted = models.BooleanField(default=False)
    trusted_until = models.DateTimeField(null=True, blank=True)
    last_active = models.DateTimeField(default=timezone.now)
    login_time = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "device_id")]
        indexes = [
            models.Index(fields=["user", "last_active"]),
            models.Index(fields=["user", "is_trusted"]),
        ]
        ordering = ["-last_active"]

    def __str__(self):
        return f"{self.device_name or self.model or self.device_id} ({self.user_id})"

    @property
    def is_trusted_active(self) -> bool:
        if not self.is_trusted:
            return False
        if self.trusted_until and self.trusted_until < timezone.now():
            return False
        return True


class UserSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    device = models.ForeignKey(
        UserDevice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
    )
    refresh_jti = models.CharField(max_length=64, unique=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["refresh_jti"]),
        ]
        ordering = ["-last_active"]

    def revoke(self):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.save(update_fields=["is_active", "revoked_at"])


class LoginHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_history")
    session = models.ForeignKey(
        UserSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="login_entries",
    )
    device = models.ForeignKey(
        UserDevice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="login_entries",
    )
    success = models.BooleanField(default=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    location = models.CharField(max_length=128, blank=True)
    device_name = models.CharField(max_length=128, blank=True)
    browser = models.CharField(max_length=64, blank=True)
    os_name = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    failure_reason = models.CharField(max_length=128, blank=True)
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Login history"
        indexes = [models.Index(fields=["user", "-created_at"])]
        ordering = ["-created_at"]


class SecurityEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="security_events")
    event_type = models.CharField(max_length=32, choices=SecurityEventType.choices)
    title = models.CharField(max_length=128)
    message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "is_read"]),
        ]
        ordering = ["-created_at"]


class BiometricCredential(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="biometric_credentials")
    device = models.ForeignKey(
        UserDevice,
        on_delete=models.CASCADE,
        related_name="biometric_credentials",
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    is_enabled = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "is_enabled"])]

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @classmethod
    def issue_token(cls, user, device) -> str:
        plain = secrets.token_urlsafe(48)
        cls.objects.filter(user=user, device=device, is_enabled=True).update(
            is_enabled=False,
            revoked_at=timezone.now(),
        )
        cls.objects.create(
            user=user,
            device=device,
            token_hash=cls.hash_token(plain),
        )
        return plain
