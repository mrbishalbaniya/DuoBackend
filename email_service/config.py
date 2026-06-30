"""Resolve email configuration from env + admin overrides."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from duo_project.runtime_config import get_integration_settings


@dataclass(frozen=True)
class EmailConfig:
    delivery: str
    host: str
    port: int
    use_tls: bool
    use_ssl: bool
    username: str
    password: str
    brevo_api_key: str
    resend_api_key: str
    from_email: str
    from_name: str
    brand_logo_url: str
    brand_primary_color: str
    footer_text: str
    social_links: str
    smtp_timeout: int


def get_email_config() -> EmailConfig:
    cfg = get_integration_settings()
    return EmailConfig(
        delivery=(cfg.email_delivery or "smtp").lower(),
        host=cfg.email_host or "smtp-relay.brevo.com",
        port=int(cfg.email_port or 587),
        use_tls=cfg.email_use_tls,
        use_ssl=cfg.email_use_ssl,
        username=cfg.email_host_user or "",
        password=cfg.email_host_password or "",
        brevo_api_key=cfg.brevo_api_key or "",
        resend_api_key=cfg.resend_api_key or "",
        from_email=cfg.default_from_email or "",
        from_name=cfg.email_from_name or "SajiloWork",
        brand_logo_url=cfg.email_brand_logo_url or "",
        brand_primary_color=cfg.email_brand_primary_color or "#6366f1",
        footer_text=cfg.email_footer_text or "© SajiloWork. All rights reserved.",
        social_links=cfg.email_social_links or "",
        smtp_timeout=int(getattr(settings, "EMAIL_SMTP_TIMEOUT", 15)),
    )


def format_from_address(config: EmailConfig) -> str:
    from email.utils import formataddr
    import re

    raw = (config.from_email or "").strip()
    name = (config.from_name or "").strip()

    if not raw:
        return ""

    match = re.match(r"^(.*?)\s*<([^>]+)>$", raw)
    if match:
        email = match.group(2).strip()
        embedded_name = match.group(1).strip().strip('"')
        display_name = name or embedded_name
        return formataddr((display_name, email)) if display_name else email

    return formataddr((name, raw)) if name else raw
