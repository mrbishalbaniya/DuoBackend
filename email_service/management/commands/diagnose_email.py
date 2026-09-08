from django.core.management.base import BaseCommand

from email_service.config import get_email_config, format_from_address
from email_service.credentials import smtp_configured
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

        self.stdout.write(f"SMTP host: {cfg.host}:{cfg.port} (TLS={cfg.use_tls}, SSL={cfg.use_ssl})")
        self.stdout.write(f"SMTP user: {cfg.username or '(not set)'}")
        smtp_ok = smtp_configured(cfg.host, cfg.username, cfg.password)
        self.stdout.write(f"SMTP password: {'configured' if smtp_ok else 'missing or invalid'}")
        self.stdout.write(f"From: {format_from_address(cfg)}")

        chain = _resolve_provider_chain(cfg)
        if not chain:
            self.stdout.write(
                self.style.ERROR(
                    "Google SMTP is not fully configured. Set the host, username, and app password "
                    "in Admin → Integration settings."
                )
            )
            return

        self.stdout.write(self.style.SUCCESS(f"Provider chain: {' -> '.join(chain)}"))

        recipient = options.get("send")
        if recipient:
            ok, message = send_test_email(recipient)
            if ok:
                self.stdout.write(self.style.SUCCESS(message))
            else:
                self.stdout.write(self.style.ERROR(f"Test failed: {message}"))
