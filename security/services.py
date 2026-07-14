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
    SecurityAlertSeverity,
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
FAILED_LOGIN_WINDOW_SECONDS = 900
FAILED_LOGIN_SUSPICIOUS_THRESHOLD = 5

_SEVERITY_BY_EVENT = {
    SecurityEventType.NEW_LOGIN: SecurityAlertSeverity.INFO,
    SecurityEventType.NEW_DEVICE: SecurityAlertSeverity.WARNING,
    SecurityEventType.PASSWORD_CHANGED: SecurityAlertSeverity.WARNING,
    SecurityEventType.TWO_FA_ENABLED: SecurityAlertSeverity.INFO,
    SecurityEventType.TWO_FA_DISABLED: SecurityAlertSeverity.CRITICAL,
    SecurityEventType.BIOMETRIC_ENABLED: SecurityAlertSeverity.INFO,
    SecurityEventType.BIOMETRIC_DISABLED: SecurityAlertSeverity.INFO,
    SecurityEventType.DEVICE_LOGOUT: SecurityAlertSeverity.INFO,
    SecurityEventType.LOGOUT_ALL: SecurityAlertSeverity.WARNING,
    SecurityEventType.DEVICE_TRUSTED: SecurityAlertSeverity.INFO,
    SecurityEventType.DEVICE_UNTRUSTED: SecurityAlertSeverity.INFO,
    SecurityEventType.SUSPICIOUS_LOGIN: SecurityAlertSeverity.CRITICAL,
    SecurityEventType.FAILED_LOGIN: SecurityAlertSeverity.WARNING,
    SecurityEventType.BACKUP_CODES_REGENERATED: SecurityAlertSeverity.WARNING,
}


def _event_title(event_type: str) -> str:
    return dict(SecurityEventType.choices).get(event_type, "Security alert")


def _parse_location(raw: str) -> tuple[str, str, str]:
    text = (raw or "").strip()
    if not text:
        return "", "", ""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) >= 2:
        return text, parts[-1], parts[0]
    return text, "", text


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
        score_data = self.compute_security_score(user, current_device_id=current_device_id)

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
            "backup_codes_remaining": self.remaining_backup_codes(user),
            "security_score": score_data["score"],
            "recommendations": score_data["recommendations"],
            "email_verified": score_data["checks"]["email_verified"],
            "phone_verified": score_data["checks"]["phone_verified"],
            "trusted_device_active": score_data["checks"]["trusted_device"],
            "recent_suspicious": not score_data["checks"]["no_suspicious"],
        }

    def compute_security_score(self, user, *, current_device_id: str = "") -> dict:
        profile = getattr(user, "profile", None)
        tfa = self.get_or_create_2fa(user)
        biometric = BiometricCredential.objects.filter(
            user=user, is_enabled=True, revoked_at__isnull=True
        ).exists()
        email_verified = bool(getattr(profile, "is_verified", False)) or bool(
            getattr(user, "email", None)
        )
        phone = ""
        if profile is not None:
            phone = f"{getattr(profile, 'phone_country_code', '') or ''}{getattr(profile, 'phone_number', '') or ''}".strip()
        phone_verified = bool(phone)
        has_password = user.has_usable_password()
        trusted = False
        if current_device_id:
            device = UserDevice.objects.filter(user=user, device_id=current_device_id).first()
            trusted = bool(device and device.is_trusted_active)
        else:
            trusted = UserDevice.objects.filter(user=user, is_trusted=True).exists()

        recent_suspicious = SecurityEvent.objects.filter(
            user=user,
            event_type=SecurityEventType.SUSPICIOUS_LOGIN,
            created_at__gte=timezone.now() - timedelta(days=7),
        ).exists()
        recent_failures = SecurityEvent.objects.filter(
            user=user,
            event_type=SecurityEventType.FAILED_LOGIN,
            created_at__gte=timezone.now() - timedelta(days=1),
        ).count()

        checks = {
            "strong_password": has_password,
            "email_verified": email_verified,
            "phone_verified": phone_verified,
            "two_factor": tfa.is_enabled,
            "biometric": biometric,
            "trusted_device": trusted,
            "no_suspicious": not recent_suspicious and recent_failures < FAILED_LOGIN_SUSPICIOUS_THRESHOLD,
        }
        weights = {
            "strong_password": 15,
            "email_verified": 15,
            "phone_verified": 10,
            "two_factor": 30,
            "biometric": 10,
            "trusted_device": 10,
            "no_suspicious": 10,
        }
        score = sum(weights[key] for key, ok in checks.items() if ok)

        recommendations: list[dict] = []
        if not checks["two_factor"]:
            recommendations.append(
                {
                    "id": "enable_2fa",
                    "title": "Enable Two-Factor Authentication",
                    "description": "Protect your account with email OTP or an authenticator app.",
                    "action": "two_factor",
                }
            )
        if not checks["email_verified"]:
            recommendations.append(
                {
                    "id": "verify_email",
                    "title": "Verify Email Address",
                    "description": "Confirm your email so we can reach you about security changes.",
                    "action": "email",
                }
            )
        if not checks["phone_verified"]:
            recommendations.append(
                {
                    "id": "verify_phone",
                    "title": "Verify Phone Number",
                    "description": "Add a phone number for account recovery and alerts.",
                    "action": "phone",
                }
            )
        if not checks["biometric"]:
            recommendations.append(
                {
                    "id": "enable_biometric",
                    "title": "Enable Biometric Login",
                    "description": "Use fingerprint or face unlock for faster secure sign-in.",
                    "action": "biometric",
                }
            )
        if UserDevice.objects.filter(user=user).count() > 1:
            recommendations.append(
                {
                    "id": "review_devices",
                    "title": "Review Active Devices",
                    "description": "Sign out of devices you no longer recognize.",
                    "action": "devices",
                }
            )

        return {"score": score, "checks": checks, "recommendations": recommendations}

    def verify_password(self, user, password: str) -> bool:
        if not user.has_usable_password():
            return False
        return user.check_password(password)

    # ── 2FA setup ──────────────────────────────────────────────

    def setup_totp(self, user) -> dict:
        tfa = self.get_or_create_2fa(user)
        secret = generate_totp_secret()
        tfa.set_totp_secret(secret)
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
            verified = verify_totp(tfa.get_totp_secret(), code)
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
        tfa.set_totp_secret("")
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

    def login_requires_2fa(self, user, request=None) -> bool:
        tfa = TwoFactorSettings.objects.filter(user=user, is_enabled=True).first()
        if tfa is None:
            return False
        if request is not None:
            info = extract_device_info(request)
            if info.device_id:
                device = UserDevice.objects.filter(user=user, device_id=info.device_id).first()
                if device and device.is_trusted_active:
                    return False
        return True

    def create_login_challenge(self, user) -> str:
        token = secrets.token_urlsafe(32)
        tfa = TwoFactorSettings.objects.get(user=user, is_enabled=True)
        cache.set(
            f"security_2fa_login:{token}",
            {"user_id": user.id, "method": tfa.method},
            CHALLENGE_TTL_SECONDS,
        )
        if tfa.method == TwoFactorMethod.EMAIL:
            try:
                self.send_login_2fa_otp(token)
            except Exception:
                pass
        return token

    def complete_login_challenge(self, challenge_token: str, code: str, request) -> User:
        payload = cache.get(f"security_2fa_login:{challenge_token}")
        if not payload:
            raise ValueError("Challenge expired or invalid.")

        user = User.objects.get(id=payload["user_id"])
        tfa = TwoFactorSettings.objects.get(user=user, is_enabled=True)
        verified = False

        if tfa.method == TwoFactorMethod.TOTP:
            verified = verify_totp(tfa.get_totp_secret(), code)
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
        location, country, city = _parse_location(info.location)

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
                "location": location,
                "country": country,
                "city": city,
                "push_token": info.push_token,
            },
        )
        if not created:
            device.device_name = info.device_name or device.device_name
            device.model = info.model or device.model
            device.os_version = info.os_version or device.os_version
            device.app_version = info.app_version or device.app_version
            device.ip_address = ip or device.ip_address
            if location:
                device.location = location
                device.country = country or device.country
                device.city = city or device.city
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
        location, country, city = _parse_location(info.location)

        device = None
        session = None
        if success and refresh_token:
            session = self.create_session(user, request, refresh_token)
            device = session.device
            is_current = True
            self._detect_suspicious_login(user, request, device=device)
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
            self._maybe_flag_brute_force(user, ip_address=ip)

        LoginHistory.objects.filter(user=user, is_current=True).update(is_current=False)
        return LoginHistory.objects.create(
            user=user,
            session=session,
            device=device,
            success=success,
            ip_address=ip,
            location=location or (device.location if device else ""),
            country=country or (device.country if device else ""),
            city=city or (device.city if device else ""),
            device_name=info.device_name or info.model or browser,
            browser=browser,
            os_name=info.os_version or os_name,
            user_agent=ua[:512],
            failure_reason=reason,
            event_type="login" if success else "failed_login",
            is_current=is_current and success,
        )

    def record_failed_password_login(self, request, *, username: str = "") -> None:
        """Record anonymous/failed credential attempt when user can be resolved."""
        from django.contrib.auth import get_user_model

        UserModel = get_user_model()
        user = UserModel.objects.filter(username=username).first() or UserModel.objects.filter(
            email__iexact=username
        ).first()
        if user is None:
            return
        self.record_login(user, request, success=False, reason="Invalid credentials")

    def _detect_suspicious_login(self, user, request, *, device: UserDevice | None = None) -> None:
        if device is None:
            return
        previous = (
            LoginHistory.objects.filter(user=user, success=True)
            .exclude(device=device)
            .order_by("-created_at")
            .first()
        )
        if previous and previous.country and device.country and previous.country != device.country:
            self._log_event(
                user,
                SecurityEventType.SUSPICIOUS_LOGIN,
                f"Login from a new country: {device.country}.",
                ip_address=get_client_ip(request),
                metadata={"country": device.country, "previous_country": previous.country},
            )

    def _maybe_flag_brute_force(self, user, *, ip_address: str | None = None) -> None:
        since = timezone.now() - timedelta(seconds=FAILED_LOGIN_WINDOW_SECONDS)
        failures = SecurityEvent.objects.filter(
            user=user,
            event_type=SecurityEventType.FAILED_LOGIN,
            created_at__gte=since,
        ).count()
        if failures >= FAILED_LOGIN_SUSPICIOUS_THRESHOLD:
            self._log_event(
                user,
                SecurityEventType.SUSPICIOUS_LOGIN,
                f"Too many failed login attempts ({failures}) in a short period.",
                ip_address=ip_address,
                metadata={"failures": failures},
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

    def delete_event(self, user, event_id: int) -> None:
        deleted, _ = SecurityEvent.objects.filter(id=event_id, user=user).delete()
        if not deleted:
            raise SecurityEvent.DoesNotExist()

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
        severity = _SEVERITY_BY_EVENT.get(event_type, SecurityAlertSeverity.INFO)
        event = SecurityEvent.objects.create(
            user=user,
            event_type=event_type,
            title=_event_title(event_type),
            message=message,
            ip_address=ip_address,
            severity=severity,
            metadata=metadata or {},
        )
        self._dispatch_security_push(user, event)
        return event

    def _dispatch_security_push(self, user, event: SecurityEvent) -> None:
        push_types = {
            SecurityEventType.NEW_LOGIN,
            SecurityEventType.NEW_DEVICE,
            SecurityEventType.PASSWORD_CHANGED,
            SecurityEventType.TWO_FA_DISABLED,
            SecurityEventType.SUSPICIOUS_LOGIN,
            SecurityEventType.FAILED_LOGIN,
        }
        if event.event_type not in push_types:
            return
        try:
            from notifications.constants import SECURITY_ALERT
            from notifications.services.notification_service import send_push_notification

            send_push_notification(
                user=user,
                title=event.title,
                body=event.message[:180],
                notification_type=SECURITY_ALERT,
                data={
                    "type": SECURITY_ALERT,
                    "event_type": event.event_type,
                    "event_id": str(event.id),
                    "route": "/security/alerts",
                },
            )
        except Exception:
            pass


security_service = SecurityService()
