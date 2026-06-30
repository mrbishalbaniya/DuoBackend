import logging
import os
import re

import requests
from django.core.mail import get_connection, send_mail

from duo_project.runtime_config import get_integration_settings

logger = logging.getLogger(__name__)

FROM_EMAIL_RE = re.compile(r"^(.*?)\s*<([^>]+)>$")


def _parse_from_email(raw: str, fallback_email: str = "") -> tuple[str, str]:
    text = (raw or "").strip()
    match = FROM_EMAIL_RE.match(text)
    if match:
        name = match.group(1).strip().strip('"') or "Duo"
        return name, match.group(2).strip()
    if text and "@" in text:
        return "Duo", text
    if fallback_email:
        return "Duo", fallback_email
    return "Duo", ""


def _send_via_resend(
    *,
    api_key: str,
    from_email: str,
    recipient_list: list[str],
    subject: str,
    message: str,
) -> None:
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "from": from_email,
            "to": recipient_list,
            "subject": subject,
            "text": message,
        },
        timeout=15,
    )
    if response.status_code >= 400:
        logger.warning("Resend API error %s: %s", response.status_code, response.text)
        raise ValueError(
            "Resend rejected the email. Verify API key and sender domain in Integration settings. "
            f"({response.text[:160]})"
        )


def _send_via_brevo(
    *,
    api_key: str,
    sender_name: str,
    sender_email: str,
    recipient_list: list[str],
    subject: str,
    message: str,
) -> None:
    response = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
            "accept": "application/json",
        },
        json={
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": email} for email in recipient_list],
            "subject": subject,
            "textContent": message,
        },
        timeout=15,
    )
    if response.status_code >= 400:
        logger.warning("Brevo API error %s: %s", response.status_code, response.text)
        raise ValueError(
            "Brevo rejected the email. Verify API key and confirm the sender email in Brevo. "
            f"({response.text[:160]})"
        )


def _send_via_smtp(
    *,
    host: str,
    port: int,
    use_tls: bool,
    host_user: str,
    host_password: str,
    from_email: str,
    recipient_list: list[str],
    subject: str,
    message: str,
) -> None:
    connection = get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host=host,
        port=port,
        username=host_user,
        password=host_password,
        use_tls=use_tls,
        timeout=15,
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=from_email,
        recipient_list=recipient_list,
        fail_silently=False,
        connection=connection,
    )


def _running_on_render() -> bool:
    return bool(os.environ.get("RENDER"))


def _production_email_help() -> str:
    return (
        "Email is not configured for production. Render blocks Gmail SMTP. "
        "In Admin → Integration settings choose Brevo or Resend, add the API key, "
        "and set Default from email. Brevo works with a verified Gmail sender."
    )


def send_configured_mail(
    *,
    subject: str,
    message: str,
    recipient_list: list[str],
) -> None:
    cfg = get_integration_settings()
    host_user = (cfg.email_host_user or "").strip()
    host_password = (cfg.email_host_password or "").replace(" ", "").strip()
    resend_key = (cfg.resend_api_key or "").strip()
    brevo_key = (cfg.brevo_api_key or "").strip()
    delivery = (cfg.email_delivery or "brevo").strip().lower()

    from_raw = (cfg.default_from_email or "").strip()
    if not from_raw and host_user:
        from_raw = f"Duo <{host_user}>"
    sender_name, sender_email = _parse_from_email(from_raw, host_user)

    on_render = _running_on_render()

    def try_resend() -> None:
        if not resend_key:
            raise ValueError("Resend API key is missing.")
        if not from_raw:
            raise ValueError('Set Default from email, e.g. Duo <onboarding@resend.dev>.')
        _send_via_resend(
            api_key=resend_key,
            from_email=from_raw,
            recipient_list=recipient_list,
            subject=subject,
            message=message,
        )

    def try_brevo() -> None:
        if not brevo_key:
            raise ValueError("Brevo API key is missing.")
        if not sender_email:
            raise ValueError('Set Default from email, e.g. Duo <you@gmail.com>.')
        _send_via_brevo(
            api_key=brevo_key,
            sender_name=sender_name,
            sender_email=sender_email,
            recipient_list=recipient_list,
            subject=subject,
            message=message,
        )

    def try_smtp() -> None:
        if not host_user or not host_password:
            raise ValueError("SMTP username/password are missing.")
        smtp_from = from_raw or f"Duo <{host_user}>"
        try:
            _send_via_smtp(
                host=cfg.email_host,
                port=cfg.email_port,
                use_tls=cfg.email_use_tls,
                host_user=host_user,
                host_password=host_password,
                from_email=smtp_from,
                recipient_list=recipient_list,
                subject=subject,
                message=message,
            )
        except OSError as exc:
            logger.warning("SMTP connection failed: %s", exc)
            raise ValueError(
                "Gmail SMTP cannot connect on Render free tier (ports 587/465 are blocked). "
                "Switch Email delivery to Brevo or Resend in Integration settings."
            ) from exc

    if on_render:
        order = []
        if delivery == "brevo":
            order = [try_brevo, try_resend]
        elif delivery == "resend":
            order = [try_resend, try_brevo]
        else:
            order = [try_brevo, try_resend]

        errors: list[str] = []
        for attempt in order:
            try:
                attempt()
                return
            except ValueError as exc:
                errors.append(str(exc))

        if errors:
            raise ValueError(f"{_production_email_help()} ({errors[0]})")
        raise ValueError(_production_email_help())

    if delivery == "resend" and resend_key:
        try_resend()
        return
    if delivery == "brevo" and brevo_key:
        try_brevo()
        return
    if delivery == "smtp" or (host_user and host_password):
        try_smtp()
        return
    if resend_key:
        try_resend()
        return
    if brevo_key:
        try_brevo()
        return

    raise ValueError(
        "Email is not configured. Set up Brevo/Resend API keys or SMTP credentials "
        "in Admin → Integration settings."
    )
