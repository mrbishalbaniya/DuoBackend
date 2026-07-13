from django.test import TestCase, override_settings

from email_service.config import EmailConfig
from email_service.constants import EmailEvent
from email_service.rendering import render_email_bodies
from email_service.service import _validate_recipients


class EmailRenderingTests(TestCase):
    def test_render_registration_otp(self):
        config = EmailConfig(
            delivery="nodemailer",
            host="smtp.example.com",
            port=587,
            use_tls=True,
            use_ssl=False,
            username="login@example.com",
            password="secret",
            nodemailer_relay_url="https://example.com/api/internal/email",
            email_relay_secret="relay-secret",
            resend_api_key="",
            from_email="noreply@example.com",
            from_name="SajiloWork",
            brand_logo_url="",
            brand_primary_color="#6366f1",
            footer_text="© SajiloWork",
            social_links="",
            smtp_timeout=15,
        )
        subject, text, html = render_email_bodies(
            "{{ brand_name }} verification code",
            "Your code is {{ otp_code }}",
            "",
            config,
            {"otp_code": "123456", "expiry_minutes": 10},
        )
        self.assertIn("SajiloWork", subject)
        self.assertIn("123456", text)
        self.assertIn("123456", html)

    def test_validate_recipients_rejects_invalid(self):
        self.assertEqual(_validate_recipients(["bad-email", "good@example.com"]), ["good@example.com"])
