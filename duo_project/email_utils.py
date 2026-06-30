"""Backward-compatible wrapper around the centralized email service."""

from __future__ import annotations

from email_service.constants import EmailEvent
from email_service.service import send_email


def send_configured_mail(
    *,
    subject: str,
    message: str,
    recipient_list: list[str],
    event: str = EmailEvent.GENERIC,
    html_message: str | None = None,
    context: dict | None = None,
) -> None:
    """Send mail through the configured provider (Brevo SMTP by default)."""
    for recipient in recipient_list:
        send_email(
            event=event,
            to=recipient,
            subject=subject,
            message=message,
            html_message=html_message,
            context=context,
            fail_silently=False,
        )
