"""Default email templates and event settings."""

from __future__ import annotations

from email_service.constants import EmailEvent
from email_service.models import EmailEventSetting, EmailTemplate

DEFAULT_SUBJECTS = {
    EmailEvent.REGISTRATION_OTP: "{{ brand_name }} verification code",
    EmailEvent.PASSWORD_RESET_OTP: "Reset your {{ brand_name }} password",
    EmailEvent.WELCOME: "Welcome to {{ brand_name }}",
    EmailEvent.LOGIN_VERIFICATION: "{{ brand_name }} login verification",
    EmailEvent.EMAIL_CHANGE: "Confirm your new email on {{ brand_name }}",
    EmailEvent.SUBSCRIPTION_CONFIRMED: "Payment confirmed — {{ brand_name }}",
    EmailEvent.SUBSCRIPTION_FAILED: "Payment issue — {{ brand_name }}",
    EmailEvent.MATCH_NOTIFICATION: "You have a new match on {{ brand_name }}",
    EmailEvent.ADMIN_ANNOUNCEMENT: "{{ brand_name }} announcement",
    EmailEvent.CONTACT_FORM: "New contact form message",
    EmailEvent.ACCOUNT_STATUS: "Your {{ brand_name }} account status changed",
    EmailEvent.GENERIC: "Message from {{ brand_name }}",
}

DEFAULT_TEXT_BODIES = {
    EmailEvent.REGISTRATION_OTP: (
        "Hi,\n\n"
        "Your verification code is: {{ otp_code }}\n\n"
        "This code expires in {{ expiry_minutes }} minutes.\n\n"
        "{{ footer_text }}"
    ),
    EmailEvent.PASSWORD_RESET_OTP: (
        "Hi,\n\n"
        "Your password reset code is: {{ otp_code }}\n\n"
        "This code expires in {{ expiry_minutes }} minutes.\n"
        "If you did not request this, ignore this email.\n\n"
        "{{ footer_text }}"
    ),
    EmailEvent.WELCOME: (
        "Hi {{ user_name }},\n\n"
        "Welcome to {{ brand_name }}! We're glad you're here.\n\n"
        "{{ footer_text }}"
    ),
    EmailEvent.GENERIC: (
        "Hi,\n\n"
        "{{ message }}\n\n"
        "{{ footer_text }}"
    ),
}


def ensure_default_templates() -> None:
    for event, subject in DEFAULT_SUBJECTS.items():
        EmailEventSetting.objects.get_or_create(
            event=event,
            defaults={"enabled": True, "subject_template": subject},
        )
        text_body = DEFAULT_TEXT_BODIES.get(
            event,
            "Hi,\n\n{{ message }}\n\n{{ footer_text }}",
        )
        EmailTemplate.objects.get_or_create(
            event=event,
            defaults={"subject": subject, "text_body": text_body, "html_body": ""},
        )
