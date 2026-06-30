from django.core.mail import get_connection, send_mail

from duo_project.runtime_config import get_integration_settings


def send_configured_mail(
    *,
    subject: str,
    message: str,
    recipient_list: list[str],
) -> None:
    cfg = get_integration_settings()
    host_user = (cfg.email_host_user or "").strip()
    host_password = (cfg.email_host_password or "").replace(" ", "").strip()

    if not host_user or not host_password:
        raise ValueError(
            "Email is not configured. Set SMTP credentials in Admin → Integration settings "
            "or EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in the environment."
        )

    connection = get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host=cfg.email_host,
        port=cfg.email_port,
        username=host_user,
        password=host_password,
        use_tls=cfg.email_use_tls,
        timeout=15,
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=cfg.default_from_email,
        recipient_list=recipient_list,
        fail_silently=False,
        connection=connection,
    )
