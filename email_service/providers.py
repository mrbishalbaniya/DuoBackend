"""Email delivery providers."""

from __future__ import annotations

import logging
import smtplib
import ssl
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from email_service.config import EmailConfig, format_from_address

logger = logging.getLogger(__name__)


class DeliveryResult:
    __slots__ = ("success", "provider", "message_id", "error")

    def __init__(self, success: bool, provider: str, message_id: str = "", error: str = ""):
        self.success = success
        self.provider = provider
        self.message_id = message_id
        self.error = error


class BaseProvider(ABC):
    name: str

    @abstractmethod
    def send(
        self,
        config: EmailConfig,
        *,
        to: list[str],
        subject: str,
        text_body: str,
        html_body: str,
    ) -> DeliveryResult:
        pass


class SmtpProvider(BaseProvider):
    name = "smtp"

    def send(
        self,
        config: EmailConfig,
        *,
        to: list[str],
        subject: str,
        text_body: str,
        html_body: str,
    ) -> DeliveryResult:
        from_addr = format_from_address(config)
        if not from_addr:
            return DeliveryResult(False, self.name, error="DEFAULT_FROM_EMAIL is not configured")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = ", ".join(to)
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            if config.use_ssl:
                server = smtplib.SMTP_SSL(config.host, config.port, timeout=config.smtp_timeout)
            else:
                server = smtplib.SMTP(config.host, config.port, timeout=config.smtp_timeout)
            with server:
                server.ehlo()
                if config.use_tls and not config.use_ssl:
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                if config.username:
                    server.login(config.username, config.password)
                server.sendmail(from_addr, to, msg.as_string())
            return DeliveryResult(True, self.name, message_id="smtp-ok")
        except Exception as exc:
            logger.exception("SMTP delivery failed to %s via %s:%s", to, config.host, config.port)
            return DeliveryResult(False, self.name, error=str(exc))


PROVIDERS: dict[str, BaseProvider] = {
    "smtp": SmtpProvider(),
}


def validate_smtp_credentials(config: EmailConfig) -> tuple[bool, str]:
    """Test SMTP connection without sending mail."""
    if not config.host:
        return False, "SMTP host is required"
    if not config.username:
        return False, "SMTP username is required"
    try:
        if config.use_ssl:
            server = smtplib.SMTP_SSL(config.host, config.port, timeout=config.smtp_timeout)
        else:
            server = smtplib.SMTP(config.host, config.port, timeout=config.smtp_timeout)
        with server:
            server.ehlo()
            if config.use_tls and not config.use_ssl:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            if config.username:
                server.login(config.username, config.password)
        return True, "SMTP credentials verified successfully"
    except Exception as exc:
        return False, str(exc)
