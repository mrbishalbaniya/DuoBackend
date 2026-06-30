import logging

import requests
from django.core.mail import get_connection, send_mail

from duo_project.runtime_config import get_integration_settings

logger = logging.getLogger(__name__)

RENDER_SMTP_HELP = (
    "Render free tier blocks SMTP ports 587/465. In Admin → Integration settings, "
    "set Email delivery to Resend and add a Resend API key, or upgrade Render to a paid plan."
)


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
            "Resend rejected the email. Verify your API key and sender address "
            f"in Integration settings. ({response.text[:180]})"
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


def send_configured_mail(
    *,
    subject: str,
    message: str,
    recipient_list: list[str],
) -> None:
    cfg = get_integration_settings()
    from_email = (cfg.default_from_email or "").strip()
    if not from_email and cfg.email_host_user:
        from_email = f"Duo <{cfg.email_host_user}>"

    delivery = (cfg.email_delivery or "smtp").strip().lower()
    resend_key = (cfg.resend_api_key or "").strip()
    host_user = (cfg.email_host_user or "").strip()
    host_password = (cfg.email_host_password or "").replace(" ", "").strip()

    if delivery == "resend" or (resend_key and delivery != "smtp"):
        if not resend_key:
            raise ValueError(
                "Resend is selected but no API key is configured. "
                "Add RESEND_API_KEY in Render env or Admin → Integration settings."
            )
        if not from_email:
            raise ValueError(
                'Set Default from email, e.g. Duo <onboarding@resend.dev> or your verified domain.'
            )
        _send_via_resend(
            api_key=resend_key,
            from_email=from_email,
            recipient_list=recipient_list,
            subject=subject,
            message=message,
        )
        return

    if not host_user or not host_password:
        raise ValueError(
            "Email is not configured. Set SMTP credentials or switch to Resend in "
            "Admin → Integration settings."
        )
    if not from_email:
        from_email = f"Duo <{host_user}>"

    try:
        _send_via_smtp(
            host=cfg.email_host,
            port=cfg.email_port,
            use_tls=cfg.email_use_tls,
            host_user=host_user,
            host_password=host_password,
            from_email=from_email,
            recipient_list=recipient_list,
            subject=subject,
            message=message,
        )
    except OSError as exc:
        logger.warning("SMTP connection failed: %s", exc)
        raise ValueError(RENDER_SMTP_HELP) from exc
