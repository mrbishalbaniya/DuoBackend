from django.core.management.base import BaseCommand

from email_service.config import get_email_config, format_from_address
from email_service.credentials import is_valid_brevo_api_key, is_valid_brevo_smtp_key, smtp_configured
from email_service.service import _resolve_provider_chain, send_test_email


class Command(BaseCommand):
    help = "Diagnose email configuration without printing secrets."

    def add_arguments(self, parser):
        parser.add_argument(
            "--send",
            metavar="EMAIL",
            help="Send a test email to this address after diagnostics.",
        )

    def handle(self, *args, **options):
        cfg = get_email_config()
        self.stdout.write(f"Delivery mode: {cfg.delivery}")
        self.stdout.write(f"SMTP host: {cfg.host}:{cfg.port} (TLS={cfg.use_tls})")
        self.stdout.write(f"SMTP user: {cfg.username or '(not set)'}")
        smtp_ok = smtp_configured(cfg.host, cfg.username, cfg.password)
        self.stdout.write(f"SMTP password: {'valid Brevo key' if smtp_ok else 'missing or invalid'}")
        api_ok = is_valid_brevo_api_key(cfg.brevo_api_key)
        self.stdout.write(f"Brevo API key: {'valid' if api_ok else 'missing or invalid'}")
        self.stdout.write(f"Resend API key: {'set' if cfg.resend_api_key else 'missing'}")
        self.stdout.write(f"From: {format_from_address(cfg)}")

        chain = _resolve_provider_chain(cfg)
        if not chain:
            self.stdout.write(
                self.style.ERROR(
                    "No provider is fully configured. Add Brevo SMTP login + SMTP key "
                    "or a Brevo API key in Admin → Integration settings."
                )
            )
            return

        self.stdout.write(self.style.SUCCESS(f"Provider chain: {' -> '.join(chain)}"))

        if cfg.host == "smtp.gmail.com":
            self.stdout.write(
                self.style.WARNING(
                    "SMTP host is still Gmail. Update to smtp-relay.brevo.com for Brevo."
                )
            )

        recipient = options.get("send")
        if recipient:
            ok, message = send_test_email(recipient)
            if ok:
                self.stdout.write(self.style.SUCCESS(message))
            else:
                self.stdout.write(self.style.ERROR(f"Test failed: {message}"))
