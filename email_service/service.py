"""Centralized email sending with logging, retry, and queue-ready design."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from email_service.config import EmailConfig, get_email_config
from email_service.constants import EmailEvent, EmailProvider, EmailStatus
from email_service.models import EmailEventSetting, EmailLog, EmailTemplate
from email_service.providers import PROVIDERS, DeliveryResult, validate_smtp_credentials
from email_service.rendering import render_email_bodies

logger = logging.getLogger(__name__)

_RETRYABLE_PATTERNS = (
    "timeout",
    "temporarily",
    "try again",
    "connection reset",
    "connection refused",
    "421",
    "450",
    "451",
    "452",
)

_MAX_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 1.5


def _validate_recipients(recipients: list[str]) -> list[str]:
    cleaned: list[str] = []
    for addr in recipients:
        addr = (addr or "").strip().lower()
        if not addr:
            continue
        try:
            validate_email(addr)
            cleaned.append(addr)
        except ValidationError:
            logger.warning("Skipping invalid email address: %s", addr[:3] + "***")
    return cleaned


def _is_retryable(error: str) -> bool:
    lower = error.lower()
    return any(p in lower for p in _RETRYABLE_PATTERNS)


from email_service.credentials import (
    is_valid_brevo_api_key,
    is_valid_resend_api_key,
    smtp_configured,
)


def _provider_available(name: str, config: EmailConfig) -> bool:
    normalized = name.lower()
    if normalized == "smtp":
        return smtp_configured(config.host, config.username, config.password)
    if normalized in ("brevo_api", "brevo"):
        return is_valid_brevo_api_key(config.brevo_api_key)
    if normalized in ("resend_api", "resend"):
        return is_valid_resend_api_key(config.resend_api_key)
    return False


def _normalize_provider(name: str) -> str:
    normalized = (name or "smtp").lower()
    if normalized == "brevo":
        return "brevo_api"
    if normalized == "resend":
        return "resend_api"
    return normalized


def _resolve_provider_chain(config: EmailConfig) -> list[str]:
    primary = _normalize_provider(config.delivery or "smtp")
    candidates = [primary, "smtp", "brevo_api", "resend_api"]
    chain: list[str] = []
    for name in candidates:
        if name not in chain and _provider_available(name, config):
            chain.append(name)
    return chain


def _get_event_setting(event: str) -> EmailEventSetting | None:
    try:
        return EmailEventSetting.objects.get(event=event)
    except EmailEventSetting.DoesNotExist:
        return None


def _get_template(event: str) -> EmailTemplate | None:
    try:
        return EmailTemplate.objects.get(event=event)
    except EmailTemplate.DoesNotExist:
        return None


def _log_email(
    *,
    event: str,
    recipient: str,
    subject: str,
    provider: str,
    status: str,
    attempt_count: int,
    error_message: str = "",
    provider_message_id: str = "",
) -> EmailLog:
    log = EmailLog.objects.create(
        event=event,
        recipient=recipient,
        subject=subject[:255],
        provider=provider,
        status=status,
        attempt_count=attempt_count,
        error_message=error_message[:2000],
        provider_message_id=provider_message_id[:255],
    )
    return log


def _deliver(
    config: EmailConfig,
    *,
    to: list[str],
    subject: str,
    text_body: str,
    html_body: str,
) -> DeliveryResult:
    chain = _resolve_provider_chain(config)
    if not chain:
        return DeliveryResult(
            False,
            config.delivery,
            error=(
                "No email provider is configured. Set Brevo SMTP credentials "
                "(smtp-relay.brevo.com) or a Brevo API key in Integration settings."
            ),
        )

    last_error = DeliveryResult(False, chain[0], error="No provider available")
    errors: list[str] = []
    for provider_name in chain:
        provider = PROVIDERS.get(provider_name)
        if not provider:
            continue
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            result = provider.send(
                config,
                to=to,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
            )
            if result.success:
                return result
            last_error = result
            if attempt < _MAX_ATTEMPTS and _is_retryable(result.error):
                time.sleep(_RETRY_DELAY_SECONDS * attempt)
                continue
            break
        errors.append(f"{provider_name}: {result.error}")
    combined = "; ".join(errors) if errors else last_error.error
    return DeliveryResult(False, last_error.provider, error=combined)


class EmailQueueItem:
    """Serializable payload for future Celery/RQ workers."""

    __slots__ = ("event", "recipients", "subject", "text_body", "html_body", "context")

    def __init__(
        self,
        event: str,
        recipients: list[str],
        subject: str,
        text_body: str,
        html_body: str,
        context: dict[str, Any],
    ):
        self.event = event
        self.recipients = recipients
        self.subject = subject
        self.text_body = text_body
        self.html_body = html_body
        self.context = context

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "recipients": self.recipients,
            "subject": self.subject,
            "text_body": self.text_body,
            "html_body": self.html_body,
            "context": self.context,
        }


def send_email(
    *,
    event: str = EmailEvent.GENERIC,
    to: str | list[str],
    subject: str | None = None,
    message: str | None = None,
    html_message: str | None = None,
    context: dict[str, Any] | None = None,
    fail_silently: bool = False,
    queue: bool = False,
) -> bool:
    """
    Send a transactional email through the configured provider.

    When queue=True, returns True after persisting a queued log entry (worker hook).
    """
    config = get_email_config()
    recipients = _validate_recipients([to] if isinstance(to, str) else list(to))
    if not recipients:
        if not fail_silently:
            raise ValueError("No valid recipients")
        return False

    event_setting = _get_event_setting(event)
    if event_setting and not event_setting.enabled:
        logger.info("Email event %s is disabled; skipping send to %s", event, recipients)
        for recipient in recipients:
            _log_email(
                event=event,
                recipient=recipient,
                subject=subject or "(disabled)",
                provider=EmailProvider.SMTP,
                status=EmailStatus.FAILED,
                attempt_count=0,
                error_message="Event disabled in admin",
            )
        return False

    ctx = dict(context or {})
    if message:
        ctx.setdefault("message", message)

    template = _get_template(event)
    if template and subject is None and message is None and html_message is None:
        subject_tpl = event_setting.subject_template if event_setting and event_setting.subject_template else template.subject
        subject, text_body, html_body = render_email_bodies(
            subject_tpl,
            template.text_body,
            template.html_body,
            config,
            ctx,
        )
    else:
        subject = subject or "Notification"
        text_body = message or ""
        html_body = html_message or ""
        if not html_body and text_body:
            from email_service.rendering import text_to_html_paragraphs, wrap_html_body

            html_body = wrap_html_body(text_to_html_paragraphs(text_body), config, preview_title=subject)

    if queue:
        from duo_project.tasks.email import queue_email

        for recipient in recipients:
            _log_email(
                event=event,
                recipient=recipient,
                subject=subject,
                provider=config.delivery,
                status=EmailStatus.QUEUED,
                attempt_count=0,
            )
        queue_email(
            event=event,
            to=to,
            subject=subject,
            message=message,
            html_message=html_message,
            context=ctx,
        )
        return True

    success = True
    for recipient in recipients:
        result = _deliver(
            config,
            to=[recipient],
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )
        status = EmailStatus.SENT if result.success else EmailStatus.FAILED
        if not result.success and _is_retryable(result.error):
            status = EmailStatus.RETRIED
        _log_email(
            event=event,
            recipient=recipient,
            subject=subject,
            provider=result.provider,
            status=status,
            attempt_count=_MAX_ATTEMPTS if status == EmailStatus.RETRIED else 1,
            error_message="" if result.success else result.error,
            provider_message_id=result.message_id,
        )
        if not result.success:
            success = False
            logger.error(
                "Email failed [%s] to %s via %s: %s",
                event,
                recipient,
                result.provider,
                result.error,
            )

    if not success and not fail_silently:
        failed = EmailLog.objects.filter(
            event=event, recipient__in=recipients, status=EmailStatus.FAILED
        ).order_by("-created_at").first()
        detail = failed.error_message if failed and failed.error_message else "Unknown error"
        raise RuntimeError(
            f"Email delivery failed: {detail} "
            "(Admin → Integration settings → Email delivery / Brevo SMTP)"
        )
    return success


def send_test_email(to: str) -> tuple[bool, str]:
    config = get_email_config()
    recipients = _validate_recipients([to])
    if not recipients:
        return False, "Invalid recipient email address"

    subject = f"Test email from {config.from_name or 'SajiloWork'}"
    text_body = (
        "This is a test email from your SMTP configuration.\n\n"
        "If you received this message, your email integration is working correctly."
    )
    from email_service.rendering import text_to_html_paragraphs, wrap_html_body

    html_body = wrap_html_body(text_to_html_paragraphs(text_body), config, preview_title=subject)

    result = _deliver(
        config,
        to=recipients,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )
    for recipient in recipients:
        _log_email(
            event=EmailEvent.GENERIC,
            recipient=recipient,
            subject=subject,
            provider=result.provider,
            status=EmailStatus.SENT if result.success else EmailStatus.FAILED,
            attempt_count=1,
            error_message="" if result.success else result.error,
            provider_message_id=result.message_id,
        )
    if result.success:
        return True, f"Test email sent via {result.provider}"
    return False, result.error


def test_smtp_configuration(config: EmailConfig | None = None) -> tuple[bool, str]:
    cfg = config or get_email_config()
    if cfg.delivery in ("brevo_api", "brevo"):
        if not cfg.brevo_api_key:
            return False, "Brevo API key is required for Brevo API delivery"
        return True, "Brevo API key is configured (use Test Email to verify delivery)"
    if cfg.delivery in ("resend", "resend_api"):
        if not cfg.resend_api_key:
            return False, "Resend API key is required for Resend delivery"
        return True, "Resend API key is configured (use Test Email to verify delivery)"
    return validate_smtp_credentials(cfg)
