import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import models
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from email_service.constants import EmailEvent
from email_service.service import send_email

from .device_utils import ClientDeviceInfo, extract_device_info, get_client_ip, parse_user_agent
from .models import (
    BackupCode,
    BiometricCredential,
    DevicePlatform,
    LoginHistory,
    SecurityEvent,
    SecurityEventType,
    TwoFactorMethod,
    TwoFactorSettings,
    UserDevice,
    UserSession,
)
from .totp import build_otpauth_uri, generate_totp_secret, verify_totp

User = get_user_model()

OTP_TTL_SECONDS = 600
CHALLENGE_TTL_SECONDS = 300


def _event_title(event_type: str) -> str:
    return dict(SecurityEventType.choices).get(event_type, "Security alert")


class SecurityService:
    def get_or_create_2fa(self, user) -> TwoFactorSettings:
        settings_obj, _ = TwoFactorSettings.objects.get_or_create(user=user)
        return settings_obj

    def overview(self, user, *, current_device_id: str = "", current_jti: str = "") -> dict:
        tfa = self.get_or_create_2fa(user)
        devices = UserDevice.objects.filter(user=user)
        sessions = UserSession.objects.filter(user=user, is_active=True)
        unread = SecurityEvent.objects.filter(user=user, is_read=False).count()
        biometric = BiometricCredential.objects.filter(
            user=user, is_enabled=True, revoked_at__isnull=True
        ).exists()

        return {
            "two_factor_enabled": tfa.is_enabled,
            "two_factor_method": tfa.method or None,
            "biometric_enabled": biometric,
            "active_devices": devices.count(),
            "active_sessions": sessions.count(),
            "unread_alerts": unread,
            "remember_device_days": tfa.remember_device_days,
            "current_device_id": current_device_id,
            "has_backup_codes": BackupCode.objects.filter(
                user=user, used_at__isnull=True
            ).exists(),
        }

    def verify_password(self, user, password: str) -> bool:
        if not user.has_usable_password():
            return False
        return user.check_password(password)

    # ── 2FA setup ──────────────────────────────────────────────

    def setup_totp(self, user) -> dict:
        tfa = self.get_or_create_2fa(user)
        secret = generate_totp_secret()
        tfa.totp_secret = secret
        tfa.method = TwoFactorMethod.TOTP
        tfa.is_enabled = False
        tfa.save(update_fields=["totp_secret", "method", "is_enabled", "updated_at"])
        email = user.email or user.username
        return {
            "secret": secret,
            "otpauth_uri": build_otpauth_uri(secret=secret, email=email),
        }

    def send_2fa_email_otp(self, user) -> None:
        tfa = self.get_or_create_2fa(user)
        tfa.method = TwoFactorMethod.EMAIL
        tfa.is_enabled = False
        tfa.save(update_fields=["method", "is_enabled", "updated_at"])

        code = "".join(secrets.choice("0123456789") for _ in range(6))
        cache.set(f"security_2fa_setup:{user.id}", code, OTP_TTL_SECONDS)
        send_email(
            event=EmailEvent.LOGIN_VERIFICATION,
            to=user.email or user.username,
            context={
                "otp_code": code,
                "expiry_minutes": OTP_TTL_SECONDS // 60,
            },
            fail_silently=False,
            queue=True,
        )

    def verify_and_enable_2fa(self, user, code: str) -> list[str]:
        tfa = self.get_or_create_2fa(user)
        verified = False

        if tfa.method == TwoFactorMethod.TOTP:
            verified = verify_totp(tfa.totp_secret, code)
        elif tfa.method == TwoFactorMethod.EMAIL:
            stored = cache.get(f"security_2fa_setup:{user.id}")
            verified = stored and stored == code.strip()
            if verified:
                cache.delete(f"security_2fa_setup:{user.id}")

        if not verified:
            raise ValueError("Invalid verification code.")

        tfa.is_enabled = True
        tfa.save(update_fields=["is_enabled", "updated_at"])
        backup_codes = BackupCode.generate_codes(user)
        self._log_event(
            user,
            SecurityEventType.TWO_FA_ENABLED,
            f"Two-factor authentication enabled via {tfa.method}.",
        )
        return backup_codes

    def disable_2fa(self, user, password: str) -> None:
        if not self.verify_password(user, password):
            raise ValueError("Incorrect password.")
        tfa = self.get_or_create_2fa(user)
        tfa.is_enabled = False
        tfa.totp_secret = ""
        tfa.method = ""
        tfa.save(update_fields=["is_enabled", "totp_secret", "method", "updated_at"])
        BackupCode.objects.filter(user=user).delete()
        self._log_event(user, SecurityEventType.TWO_FA_DISABLED, "Two-factor authentication disabled.")

    def regenerate_backup_codes(self, user, password: str) -> list[str]:
        if not self.verify_password(user, password):
            raise ValueError("Incorrect password.")
        tfa = self.get_or_create_2fa(user)
        if not tfa.is_enabled:
            raise ValueError("Two-factor authentication is not enabled.")
        codes = BackupCode.generate_codes(user)
        self._log_event(
            user,
            SecurityEventType.BACKUP_CODES_REGENERATED,
            "Backup recovery codes were regenerated.",
        )
        return codes

    def remaining_backup_codes(self, user) -> int:
        return BackupCode.objects.filter(user=user, used_at__isnull=True).count()

    # ── 2FA login challenge ────────────────────────────────────

    def login_requires_2fa(self, user) -> bool:
        tfa = TwoFactorSettings.objects.filter(user=user, is_enabled=True).first()
        return tfa is not None

    def create_login_challenge(self, user) -> str:
        token = secrets.token_urlsafe(32)
        tfa = TwoFactorSettings.objects.get(user=user, is_enabled=True)
        cache.set(
            f"security_2fa_login:{token}",
            {"user_id": user.id, "method": tfa.method},
            CHALLENGE_TTL_SECONDS,
        )
        return token

    def complete_login_challenge(self, challenge_token: str, code: str, request) -> User:
        payload = cache.get(f"security_2fa_login:{challenge_token}")
        if not payload:
            raise ValueError("Challenge expired or invalid.")

        user = User.objects.get(id=payload["user_id"])
        tfa = TwoFactorSettings.objects.get(user=user, is_enabled=True)
        verified = False

        if tfa.method == TwoFactorMethod.TOTP:
            verified = verify_totp(tfa.totp_secret, code)
        elif tfa.method == TwoFactorMethod.EMAIL:
            stored = cache.get(f"security_2fa_login_otp:{user.id}")
            verified = stored and stored == code.strip()

        if not verified and BackupCode.hash_code(code) in list(
            BackupCode.objects.filter(user=user, used_at__isnull=True).values_list(
                "code_hash", flat=True
            )
        ):
            BackupCode.objects.filter(
                user=user, code_hash=BackupCode.hash_code(code), used_at__isnull=True
            ).update(used_at=timezone.now())
            verified = True

        if not verified:
            self.record_login(user, request, success=False, reason="Invalid 2FA code")
            raise ValueError("Invalid verification code.")

        cache.delete(f"security_2fa_login:{challenge_token}")
        cache.delete(f"security_2fa_login_otp:{user.id}")
        return user

    def send_login_2fa_otp(self, challenge_token: str) -> None:
        payload = cache.get(f"security_2fa_login:{challenge_token}")
        if not payload:
            raise ValueError("Challenge expired or invalid.")
        user = User.objects.get(id=payload["user_id"])
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        cache.set(f"security_2fa_login_otp:{user.id}", code, OTP_TTL_SECONDS)
        send_email(
            event=EmailEvent.LOGIN_VERIFICATION,
            to=user.email or user.username,
            context={"otp_code": code, "expiry_minutes": OTP_TTL_SECONDS // 60},
            fail_silently=False,
            queue=True,
        )

    # ── Sessions & devices ─────────────────────────────────────

    def upsert_device(self, user, info: ClientDeviceInfo, request) -> UserDevice:
        if not info.device_id:
            info.device_id = secrets.token_hex(16)

        ip = get_client_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")
        browser, os_name = parse_user_agent(ua)

        device, created = UserDevice.objects.get_or_create(
            user=user,
            device_id=info.device_id,
            defaults={
                "device_name": info.device_name or info.model or "Unknown device",
                "model": info.model,
                "platform": info.platform if info.platform in DevicePlatform.values else DevicePlatform.UNKNOWN,
                "os_version": info.os_version or os_name,
                "app_version": info.app_version,
                "browser": browser if info.platform == "web" else "",
                "ip_address": ip,
                "location": info.location,
                "push_token": info.push_token,
            },
        )
        if not created:
            device.device_name = info.device_name or device.device_name
            device.model = info.model or device.model
            device.os_version = info.os_version or device.os_version
            device.app_version = info.app_version or device.app_version
            device.ip_address = ip or device.ip_address
            device.location = info.location or device.location
            device.push_token = info.push_token or device.push_token
            device.last_active = timezone.now()
            device.save()

        if created:
            self._log_event(
                user,
                SecurityEventType.NEW_DEVICE,
                f"New device signed in: {device.device_name}.",
                ip_address=ip,
                metadata={"device_id": device.device_id},
            )
        return device

    def create_session(self, user, request, refresh_token_str: str) -> UserSession:
        info = extract_device_info(request)
        device = self.upsert_device(user, info, request)
        refresh = RefreshToken(refresh_token_str)
        jti = str(refresh["jti"])

        session, _ = UserSession.objects.update_or_create(
            refresh_jti=jti,
            defaults={
                "user": user,
                "device": device,
                "ip_address": get_client_ip(request),
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:512],
                "is_active": True,
                "last_active": timezone.now(),
                "revoked_at": None,
            },
        )
        return session

    def record_login(
        self,
        user,
        request,
        *,
        success: bool = True,
        refresh_token: str = "",
        reason: str = "",
        is_current: bool = False,
    ) -> LoginHistory:
        info = extract_device_info(request)
        ip = get_client_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")
        browser, os_name = parse_user_agent(ua)

        device = None
        session = None
        if success and refresh_token:
            session = self.create_session(user, request, refresh_token)
            device = session.device
            is_current = True
            self._log_event(
                user,
                SecurityEventType.NEW_LOGIN,
                f"Successful login from {device.device_name if device else 'unknown device'}.",
                ip_address=ip,
            )
        elif not success:
            self._log_event(
                user,
                SecurityEventType.FAILED_LOGIN,
                reason or "Failed login attempt.",
                ip_address=ip,
            )

        LoginHistory.objects.filter(user=user, is_current=True).update(is_current=False)
        return LoginHistory.objects.create(
            user=user,
            session=session,
            device=device,
            success=success,
            ip_address=ip,
            location=info.location,
            device_name=info.device_name or info.model or browser,
            browser=browser,
            os_name=info.os_version or os_name,
            user_agent=ua[:512],
            failure_reason=reason,
            is_current=is_current and success,
        )

    def touch_session(self, refresh_jti: str) -> None:
        UserSession.objects.filter(refresh_jti=refresh_jti, is_active=True).update(
            last_active=timezone.now()
        )

    def is_session_active(self, refresh_jti: str) -> bool:
        if not refresh_jti:
            return True
        try:
            session = (
                UserSession.objects.filter(refresh_jti=refresh_jti)
                .only("is_active", "revoked_at")
                .first()
            )
        except Exception:
            return True
        if session is None:
            # No tracked session (legacy login or security logging unavailable).
            return True
        return session.is_active and session.revoked_at is None

    def register_access_token(self, access_jti: str, refresh_jti: str) -> None:
        if not access_jti or not refresh_jti:
            return
        from django.conf import settings

        lifetime = getattr(settings, "SIMPLE_JWT", {}).get("ACCESS_TOKEN_LIFETIME", 3600)
        ttl = int(lifetime.total_seconds()) if hasattr(lifetime, "total_seconds") else int(lifetime)
        try:
            cache.set(f"access_session:{access_jti}", refresh_jti, timeout=ttl)
        except Exception:
            pass

    def is_access_session_active(self, access_jti: str) -> bool:
        if not access_jti:
            return True
        try:
            refresh_jti = cache.get(f"access_session:{access_jti}")
        except Exception:
            return True
        if refresh_jti is None:
            return True
        return self.is_session_active(refresh_jti)

    def revoke_access_session(self, access_jti: str) -> None:
        if access_jti:
            cache.delete(f"access_session:{access_jti}")

    def revoke_session(self, user, session_id: int, *, current_jti: str = "") -> None:
        session = UserSession.objects.get(id=session_id, user=user)
        if session.refresh_jti == current_jti:
            raise ValueError("Cannot revoke the current session from this screen.")
        session.revoke()
        if session.device:
            session.device.push_token = ""
            session.device.save(update_fields=["push_token", "updated_at"])
        self._log_event(
            user,
            SecurityEventType.DEVICE_LOGOUT,
            "A device session was signed out.",
            metadata={"session_id": session_id},
        )

    def revoke_all_sessions(
        self, user, *, keep_current: bool = True, current_jti: str = ""
    ) -> int:
        qs = UserSession.objects.filter(user=user, is_active=True)
        if keep_current and current_jti:
            qs = qs.exclude(refresh_jti=current_jti)
        count = qs.count()
        now = timezone.now()
        qs.update(is_active=False, revoked_at=now)
        UserDevice.objects.filter(user=user).exclude(
            sessions__refresh_jti=current_jti, sessions__is_active=True
        ).update(push_token="")
        self._log_event(
            user,
            SecurityEventType.LOGOUT_ALL,
            f"Signed out of {count} device(s).",
        )
        return count

    def list_devices(self, user, *, current_device_id: str = "") -> list[UserDevice]:
        return list(UserDevice.objects.filter(user=user))

    def rename_device(self, user, device_id: int, name: str) -> UserDevice:
        device = UserDevice.objects.get(id=device_id, user=user)
        device.device_name = name.strip()[:128]
        device.save(update_fields=["device_name", "updated_at"])
        return device

    def trust_device(self, user, device_id: int) -> UserDevice:
        device = UserDevice.objects.get(id=device_id, user=user)
        tfa = self.get_or_create_2fa(user)
        device.is_trusted = True
        device.trusted_until = timezone.now() + timedelta(days=tfa.remember_device_days)
        device.save(update_fields=["is_trusted", "trusted_until", "updated_at"])
        self._log_event(
            user,
            SecurityEventType.DEVICE_TRUSTED,
            f"{device.device_name} marked as trusted.",
            metadata={"device_id": device.device_id},
        )
        return device

    def untrust_device(self, user, device_id: int) -> UserDevice:
        device = UserDevice.objects.get(id=device_id, user=user)
        device.is_trusted = False
        device.trusted_until = None
        device.save(update_fields=["is_trusted", "trusted_until", "updated_at"])
        self._log_event(
            user,
            SecurityEventType.DEVICE_UNTRUSTED,
            f"{device.device_name} removed from trusted devices.",
        )
        return device

    # ── Biometric ──────────────────────────────────────────────

    def enable_biometric(self, user, request, password: str) -> tuple[str, UserDevice]:
        if not self.verify_password(user, password):
            raise ValueError("Incorrect password.")
        info = extract_device_info(request)
        device = self.upsert_device(user, info, request)
        token = BiometricCredential.issue_token(user, device)
        self._log_event(user, SecurityEventType.BIOMETRIC_ENABLED, "Biometric login enabled.")
        return token, device

    def disable_biometric(self, user, password: str) -> None:
        if not self.verify_password(user, password):
            raise ValueError("Incorrect password.")
        BiometricCredential.objects.filter(user=user, is_enabled=True).update(
            is_enabled=False,
            revoked_at=timezone.now(),
        )
        self._log_event(user, SecurityEventType.BIOMETRIC_DISABLED, "Biometric login disabled.")

    def biometric_login(self, request, token: str, device_id: str) -> User | None:
        token_hash = BiometricCredential.hash_token(token)
        cred = (
            BiometricCredential.objects.select_related("user", "device")
            .filter(
                token_hash=token_hash,
                is_enabled=True,
                revoked_at__isnull=True,
                device__device_id=device_id,
            )
            .first()
        )
        if not cred:
            return None
        cred.last_used_at = timezone.now()
        cred.save(update_fields=["last_used_at"])
        cred.device.last_active = timezone.now()
        cred.device.save(update_fields=["last_active", "updated_at"])
        return cred.user

    def biometric_status(self, user, device_id: str = "") -> dict:
        qs = BiometricCredential.objects.filter(user=user, is_enabled=True, revoked_at__isnull=True)
        if device_id:
            qs = qs.filter(device__device_id=device_id)
        return {"enabled": qs.exists()}

    # ── Alerts & history ───────────────────────────────────────

    def list_events(self, user, *, unread_only: bool = False) -> list[SecurityEvent]:
        qs = SecurityEvent.objects.filter(user=user)
        if unread_only:
            qs = qs.filter(is_read=False)
        return list(qs[:50])

    def mark_event_read(self, user, event_id: int) -> SecurityEvent:
        event = SecurityEvent.objects.get(id=event_id, user=user)
        event.is_read = True
        event.save(update_fields=["is_read"])
        return event

    def mark_all_events_read(self, user) -> int:
        return SecurityEvent.objects.filter(user=user, is_read=False).update(is_read=True)

    def list_login_history(
        self, user, *, search: str = "", success_only: bool | None = None, page: int = 1, page_size: int = 20
    ) -> tuple[list[LoginHistory], int]:
        qs = LoginHistory.objects.filter(user=user)
        if search:
            qs = qs.filter(
                models.Q(device_name__icontains=search)
                | models.Q(location__icontains=search)
                | models.Q(ip_address__icontains=search)
            )
        if success_only is not None:
            qs = qs.filter(success=success_only)
        total = qs.count()
        offset = (max(page, 1) - 1) * page_size
        return list(qs.select_related("device", "session")[offset : offset + page_size]), total

    def on_password_changed(self, user, request) -> None:
        self._log_event(
            user,
            SecurityEventType.PASSWORD_CHANGED,
            "Your password was changed.",
            ip_address=get_client_ip(request),
        )

    def _log_event(
        self,
        user,
        event_type: str,
        message: str,
        *,
        ip_address: str | None = None,
        metadata: dict | None = None,
    ) -> SecurityEvent:
        return SecurityEvent.objects.create(
            user=user,
            event_type=event_type,
            title=_event_title(event_type),
            message=message,
            ip_address=ip_address,
            metadata=metadata or {},
        )


security_service = SecurityService()
