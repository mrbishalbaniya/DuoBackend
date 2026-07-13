"""Email delivery providers."""

from __future__ import annotations

import logging
import smtplib
import ssl
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import requests

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


class NodemailerRelayProvider(BaseProvider):
    """Send email via the Duo frontend Nodemailer relay (HTTPS)."""

    name = "nodemailer"

    def send(
        self,
        config: EmailConfig,
        *,
        to: list[str],
        subject: str,
        text_body: str,
        html_body: str,
    ) -> DeliveryResult:
        from django.conf import settings

        relay_url = (config.nodemailer_relay_url or "").strip()
        if not relay_url:
            frontend = getattr(settings, "FRONTEND_URL", "").strip().rstrip("/")
            if frontend:
                relay_url = f"{frontend}/api/internal/email"
        secret = (config.email_relay_secret or getattr(settings, "EMAIL_RELAY_SECRET", "") or "").strip()
        if not relay_url:
            return DeliveryResult(False, self.name, error="Nodemailer relay URL is not configured")
        if not secret:
            return DeliveryResult(
                False,
                self.name,
                error="EMAIL_RELAY_SECRET is not configured on backend or in Integration settings.",
            )

        from_addr = format_from_address(config)
        if not from_addr:
            return DeliveryResult(False, self.name, error="DEFAULT_FROM_EMAIL is not configured")

        payload: dict[str, Any] = {
            "smtp": {
                "host": config.host,
                "port": config.port,
                "secure": config.use_ssl,
                "requireTLS": config.use_tls and not config.use_ssl,
                "auth": {
                    "user": config.username,
                    "pass": config.password,
                },
            },
            "from": from_addr,
            "to": to,
            "subject": subject,
            "text": text_body,
            "html": html_body or "",
        }

        try:
            response = requests.post(
                relay_url,
                headers={
                    "Authorization": f"Bearer {secret}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=payload,
                timeout=config.smtp_timeout,
            )
            if response.status_code in (200, 201):
                data = response.json() if response.content else {}
                return DeliveryResult(True, self.name, message_id=str(data.get("messageId", "")))
            return DeliveryResult(
                False,
                self.name,
                error=f"Nodemailer relay {response.status_code}: {response.text[:500]}",
            )
        except Exception as exc:
            logger.exception("Nodemailer relay delivery failed")
            return DeliveryResult(False, self.name, error=str(exc))


class ResendApiProvider(BaseProvider):
    name = "resend_api"

    def send(
        self,
        config: EmailConfig,
        *,
        to: list[str],
        subject: str,
        text_body: str,
        html_body: str,
    ) -> DeliveryResult:
        api_key = (config.resend_api_key or "").strip()
        if not api_key:
            return DeliveryResult(False, self.name, error="Resend API key is not configured")

        from_addr = format_from_address(config)
        if not from_addr:
            return DeliveryResult(False, self.name, error="DEFAULT_FROM_EMAIL is not configured")

        payload: dict[str, Any] = {
            "from": from_addr,
            "to": to,
            "subject": subject,
            "text": text_body,
        }
        if html_body:
            payload["html"] = html_body

        try:
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=config.smtp_timeout,
            )
            if response.status_code in (200, 201):
                data = response.json() if response.content else {}
                return DeliveryResult(True, self.name, message_id=str(data.get("id", "")))
            return DeliveryResult(
                False,
                self.name,
                error=f"Resend API {response.status_code}: {response.text[:500]}",
            )
        except Exception as exc:
            logger.exception("Resend API delivery failed")
            return DeliveryResult(False, self.name, error=str(exc))


PROVIDERS: dict[str, BaseProvider] = {
    "nodemailer": NodemailerRelayProvider(),
    "smtp": SmtpProvider(),
    "resend": ResendApiProvider(),
    "resend_api": ResendApiProvider(),
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
