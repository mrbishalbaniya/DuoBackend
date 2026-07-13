from django.conf import settings
from django.core.management.base import BaseCommand
import os

from email_service.credentials import is_placeholder
from duo_project.runtime_config import invalidate_integration_cache
from duo_project.secret_fields import decrypt_secret, encrypt_secret
from site_config.models import SiteSettings


class Command(BaseCommand):
    help = "Create Integration settings and apply email defaults from environment."

    def handle(self, *args, **options):
        obj = SiteSettings.get_solo()
        updated: list[str] = []

        env_host = getattr(settings, "EMAIL_HOST", "") or ""
        env_delivery = getattr(settings, "EMAIL_DELIVERY", "") or ""
        env_user = getattr(settings, "EMAIL_HOST_USER", "") or ""
        env_password = getattr(settings, "EMAIL_HOST_PASSWORD", "") or ""
        env_relay_secret = getattr(settings, "EMAIL_RELAY_SECRET", "") or ""
        env_relay_url = getattr(settings, "NODEMAILER_RELAY_URL", "") or ""
        env_from = getattr(settings, "DEFAULT_FROM_EMAIL", "") or ""
        env_from_name = getattr(settings, "EMAIL_FROM_NAME", "") or ""

        if (not obj.email_host or obj.email_host == "smtp.gmail.com") and env_host:
            obj.email_host = env_host
            updated.append("email_host")
        elif obj.email_host == "smtp-relay.brevo.com":
            obj.email_host = env_host or ""
            updated.append("email_host")

        if env_delivery and (
            not obj.email_delivery
            or obj.email_delivery in ("resend", "brevo")
            and not decrypt_secret(obj.resend_api_key or "").strip()
        ):
            normalized_delivery = "nodemailer" if env_delivery == "brevo" else env_delivery
            if normalized_delivery != obj.email_delivery:
                obj.email_delivery = normalized_delivery
                updated.append("email_delivery")
        elif obj.email_delivery in ("resend", "brevo") and not decrypt_secret(
            obj.resend_api_key or ""
        ).strip():
            if obj.email_host_user and obj.email_host_password:
                obj.email_delivery = "nodemailer"
                updated.append("email_delivery")

        if env_user and not obj.email_host_user:
            obj.email_host_user = env_user
            updated.append("email_host_user")

        if env_password and not obj.email_host_password and not is_placeholder(env_password):
            obj.email_host_password = encrypt_secret(env_password.replace(" ", ""))
            updated.append("email_host_password")

        if env_relay_url and not obj.nodemailer_relay_url:
            obj.nodemailer_relay_url = env_relay_url.strip()
            updated.append("nodemailer_relay_url")

        if env_relay_secret and not obj.email_relay_secret and not is_placeholder(env_relay_secret):
            obj.email_relay_secret = encrypt_secret(env_relay_secret.strip())
            updated.append("email_relay_secret")

        if env_from and not obj.default_from_email:
            obj.default_from_email = env_from
            updated.append("default_from_email")

        if env_from_name and not obj.email_from_name:
            obj.email_from_name = env_from_name
            updated.append("email_from_name")

        render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
        backend_base = (
            f"https://{render_host}".rstrip("/")
            if render_host
            else getattr(settings, "BACKEND_PUBLIC_URL", "https://duobackend.onrender.com").rstrip("/")
        )
        default_success = f"{backend_base}/api/subscriptions/esewa/success/"
        default_failure = f"{backend_base}/api/subscriptions/esewa/failure/"

        env_esewa_product = getattr(settings, "ESEWA_PRODUCT_CODE", "") or ""
        if env_esewa_product and not obj.esewa_product_code:
            obj.esewa_product_code = env_esewa_product.strip()
            updated.append("esewa_product_code")

        env_esewa_secret = getattr(settings, "ESEWA_SECRET_KEY", "") or ""
        if env_esewa_secret and not obj.esewa_secret_key and not is_placeholder(env_esewa_secret):
            obj.esewa_secret_key = encrypt_secret(env_esewa_secret.strip())
            updated.append("esewa_secret_key")

        if not obj.esewa_success_url:
            obj.esewa_success_url = default_success
            updated.append("esewa_success_url")
        if not obj.esewa_failure_url:
            obj.esewa_failure_url = default_failure
            updated.append("esewa_failure_url")

        env_openweather = getattr(settings, "OPENWEATHER_API_KEY", "") or ""
        if env_openweather and not obj.openweather_api_key and not is_placeholder(env_openweather):
            obj.openweather_api_key = encrypt_secret(env_openweather.strip())
            updated.append("openweather_api_key")

        env_google_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "") or ""
        if env_google_id and env_google_id != (obj.google_client_id or "").strip():
            obj.google_client_id = env_google_id.strip()
            updated.append("google_client_id")

        env_google_secret = getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "") or ""
        if env_google_secret and not is_placeholder(env_google_secret):
            current_secret = decrypt_secret((obj.google_client_secret or "").strip())
            if env_google_secret.strip() != current_secret:
                obj.google_client_secret = encrypt_secret(env_google_secret.strip())
                updated.append("google_client_secret")

        env_google_redirect = getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", "") or ""
        if env_google_redirect and env_google_redirect.strip() != (obj.google_redirect_uri or "").strip():
            obj.google_redirect_uri = env_google_redirect.strip()
            updated.append("google_redirect_uri")

        env_google_allowed = getattr(settings, "GOOGLE_OAUTH_ALLOWED_REDIRECT_URIS", None)
        if env_google_allowed:
            allowed_csv = ",".join(uri.strip() for uri in env_google_allowed if uri.strip())
            if allowed_csv and allowed_csv != (obj.google_allowed_redirect_uris or "").strip():
                obj.google_allowed_redirect_uris = allowed_csv
                updated.append("google_allowed_redirect_uris")

        if not obj.email_port:
            obj.email_port = getattr(settings, "EMAIL_PORT", 587)
            updated.append("email_port")

        if obj.email_use_tls is None:
            obj.email_use_tls = getattr(settings, "EMAIL_USE_TLS", True)
            updated.append("email_use_tls")

        env_stun_urls = getattr(settings, "WEBRTC_STUN_URLS", None) or []
        if env_stun_urls and not (obj.webrtc_stun_urls or "").strip():
            obj.webrtc_stun_urls = ",".join(url.strip() for url in env_stun_urls if url.strip())
            updated.append("webrtc_stun_urls")

        env_turn_url = getattr(settings, "WEBRTC_TURN_URL", "") or ""
        if env_turn_url and not (obj.webrtc_turn_url or "").strip():
            obj.webrtc_turn_url = env_turn_url.strip()
            updated.append("webrtc_turn_url")

        env_turn_user = getattr(settings, "WEBRTC_TURN_USERNAME", "") or ""
        if env_turn_user and not (obj.webrtc_turn_username or "").strip():
            obj.webrtc_turn_username = env_turn_user.strip()
            updated.append("webrtc_turn_username")

        env_turn_cred = getattr(settings, "WEBRTC_TURN_CREDENTIAL", "") or ""
        if env_turn_cred and not obj.webrtc_turn_credential and not is_placeholder(env_turn_cred):
            obj.webrtc_turn_credential = encrypt_secret(env_turn_cred.strip())
            updated.append("webrtc_turn_credential")

        env_turn_secret = getattr(settings, "WEBRTC_TURN_SECRET", "") or ""
        if env_turn_secret and not obj.webrtc_turn_secret and not is_placeholder(env_turn_secret):
            obj.webrtc_turn_secret = encrypt_secret(env_turn_secret.strip())
            updated.append("webrtc_turn_secret")

        if not obj.webrtc_turn_ttl:
            obj.webrtc_turn_ttl = getattr(settings, "WEBRTC_TURN_TTL", 86400)
            updated.append("webrtc_turn_ttl")

        obj.save()
        invalidate_integration_cache()

        if updated:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Integration settings updated: {', '.join(sorted(set(updated)))}"
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("Integration settings already up to date."))

        self.stdout.write(
            f"Edit at /admin/site_config/sitesettings/{obj.pk}/change/ "
            f"(delivery={obj.email_delivery}, host={obj.email_host})"
        )
