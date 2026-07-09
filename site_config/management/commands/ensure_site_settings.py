from django.conf import settings
from django.core.management.base import BaseCommand

from email_service.credentials import is_placeholder
from duo_project.runtime_config import invalidate_integration_cache
from duo_project.secret_fields import decrypt_secret, encrypt_secret
from site_config.models import SiteSettings


class Command(BaseCommand):
    help = "Create Integration settings and apply Brevo email defaults from environment."

    def handle(self, *args, **options):
        obj = SiteSettings.get_solo()
        updated: list[str] = []

        env_host = getattr(settings, "EMAIL_HOST", "") or ""
        env_delivery = getattr(settings, "EMAIL_DELIVERY", "") or ""
        env_user = getattr(settings, "EMAIL_HOST_USER", "") or ""
        env_password = getattr(settings, "EMAIL_HOST_PASSWORD", "") or ""
        env_brevo = getattr(settings, "BREVO_API_KEY", "") or ""
        env_from = getattr(settings, "DEFAULT_FROM_EMAIL", "") or ""
        env_from_name = getattr(settings, "EMAIL_FROM_NAME", "") or ""

        if obj.email_host == "smtp.gmail.com":
            obj.email_host = env_host or "smtp-relay.brevo.com"
            updated.append("email_host")
        elif (not obj.email_host or obj.email_host == "smtp.gmail.com") and env_host:
            obj.email_host = env_host
            updated.append("email_host")

        if env_delivery and (
            not obj.email_delivery
            or obj.email_delivery == "resend"
            and not decrypt_secret(obj.resend_api_key or "").strip()
        ):
            if env_delivery != obj.email_delivery:
                obj.email_delivery = env_delivery
                updated.append("email_delivery")
        elif (
            obj.email_delivery == "resend"
            and not decrypt_secret(obj.resend_api_key or "").strip()
            and obj.email_host_user
            and obj.email_host_password
        ):
            obj.email_delivery = "smtp"
            updated.append("email_delivery")

        if env_user and not obj.email_host_user:
            obj.email_host_user = env_user
            updated.append("email_host_user")

        if env_password and not obj.email_host_password and not is_placeholder(env_password):
            obj.email_host_password = encrypt_secret(env_password.replace(" ", ""))
            updated.append("email_host_password")

        if env_brevo and not obj.brevo_api_key and not is_placeholder(env_brevo):
            obj.brevo_api_key = encrypt_secret(env_brevo.strip())
            updated.append("brevo_api_key")

        if env_from and not obj.default_from_email:
            obj.default_from_email = env_from
            updated.append("default_from_email")

        if env_from_name and not obj.email_from_name:
            obj.email_from_name = env_from_name
            updated.append("email_from_name")

        env_openweather = getattr(settings, "OPENWEATHER_API_KEY", "") or ""
        if env_openweather and not obj.openweather_api_key and not is_placeholder(env_openweather):
            obj.openweather_api_key = encrypt_secret(env_openweather.strip())
            updated.append("openweather_api_key")

        if not obj.email_port:
            obj.email_port = getattr(settings, "EMAIL_PORT", 587)
            updated.append("email_port")

        if obj.email_use_tls is None:
            obj.email_use_tls = getattr(settings, "EMAIL_USE_TLS", True)
            updated.append("email_use_tls")

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
