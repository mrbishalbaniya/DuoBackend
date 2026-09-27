from django.test import TestCase, override_settings

from email_service.config import EmailConfig
from email_service.constants import EmailEvent
from email_service.rendering import render_email_bodies
from email_service.service import _validate_recipients


class EmailRenderingTests(TestCase):
    def test_render_registration_otp(self):
        config = EmailConfig(
            host="smtp.gmail.com",
            port=587,
            use_tls=True,
            use_ssl=False,
            username="login@example.com",
            password="secret",
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

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    def test_queued_template_email_is_rendered_by_worker(self):
        """The worker must receive the caller's args, not the pre-rendered
        subject, or it skips the template and sends an empty body."""
        from unittest.mock import patch

        from email_service.defaults import ensure_default_templates
        from email_service.providers import DeliveryResult
        from email_service.service import send_email

        ensure_default_templates()
        with patch("duo_project.tasks.email.send_email_task.delay") as delay:
            send_email(
                event=EmailEvent.PASSWORD_RESET_OTP,
                to="someone@example.com",
                context={"otp_code": "654321", "expiry_minutes": 10},
                queue=True,
            )
        queued = delay.call_args.kwargs
        self.assertIsNone(queued["subject"])

        from duo_project.tasks.email import send_email_task

        with patch(
            "email_service.service._deliver", return_value=DeliveryResult(True, "smtp")
        ) as deliver:
            send_email_task(**queued)
        sent = deliver.call_args.kwargs
        self.assertIn("654321", sent["subject"])
        self.assertIn("654321", sent["text_body"])
        self.assertIn("654321", sent["html_body"])

    def test_validate_recipients_rejects_invalid(self):
        self.assertEqual(_validate_recipients(["bad-email", "good@example.com"]), ["good@example.com"])


class OtpTemplateTests(TestCase):
    """Every OTP email must actually contain the code (login emails used not to)."""

    def _config(self):
        return EmailConfig(
            host="smtp.gmail.com", port=587, use_tls=True, use_ssl=False,
            username="u@example.com", password="x", from_email="noreply@example.com",
            from_name="DuoNepal", brand_logo_url="", brand_primary_color="#6366f1",
            footer_text="© DuoNepal", social_links="", smtp_timeout=15,
        )

    def test_default_otp_templates_include_code(self):
        from email_service.defaults import DEFAULT_HTML_BODIES, DEFAULT_SUBJECTS, DEFAULT_TEXT_BODIES, OTP_EVENTS

        for event in OTP_EVENTS:
            subject, text, html = render_email_bodies(
                DEFAULT_SUBJECTS[event], DEFAULT_TEXT_BODIES[event], DEFAULT_HTML_BODIES[event],
                self._config(), {"otp_code": "482913", "expiry_minutes": 10},
            )
            with self.subTest(event=event):
                self.assertIn("482913", subject)
                self.assertIn("482913", text)
                self.assertIn("482913", html)
                self.assertIn("10 minutes", html)
                self.assertNotIn("{{", html)

    def test_legacy_login_template_is_upgraded(self):
        from email_service.defaults import ensure_default_templates
        from email_service.models import EmailTemplate

        ensure_default_templates()
        EmailTemplate.objects.filter(event=EmailEvent.LOGIN_VERIFICATION).update(
            subject="{{ brand_name }} login verification",
            text_body="Hi,\n\n{{ message }}\n\n{{ footer_text }}",
            html_body="",
        )
        ensure_default_templates()
        tpl = EmailTemplate.objects.get(event=EmailEvent.LOGIN_VERIFICATION)
        self.assertIn("otp_code", tpl.text_body)
        self.assertIn("otp_code", tpl.html_body)
        self.assertIn("otp_code", tpl.subject)

    def test_customised_template_is_left_alone(self):
        from email_service.defaults import ensure_default_templates
        from email_service.models import EmailTemplate

        ensure_default_templates()
        EmailTemplate.objects.filter(event=EmailEvent.REGISTRATION_OTP).update(
            text_body="Custom {{ otp_code }}", html_body="<p>Custom {{ otp_code }}</p>"
        )
        ensure_default_templates()
        tpl = EmailTemplate.objects.get(event=EmailEvent.REGISTRATION_OTP)
        self.assertEqual(tpl.text_body, "Custom {{ otp_code }}")


class ThemedTemplateTests(TestCase):
    def _config(self, color="#6366f1", footer="© SajiloWork. All rights reserved."):
        return EmailConfig(
            host="smtp.gmail.com", port=587, use_tls=True, use_ssl=False,
            username="u@example.com", password="x", from_email="noreply@example.com",
            from_name="DuoNepal", brand_logo_url="", brand_primary_color=color,
            footer_text=footer, social_links="", smtp_timeout=15,
        )

    def test_every_default_template_renders_in_site_theme(self):
        from email_service.defaults import DEFAULT_HTML_BODIES, DEFAULT_SUBJECTS, DEFAULT_TEXT_BODIES

        ctx = {"otp_code": "482913", "expiry_minutes": 10, "user_name": "Asha", "message": "Hello\nthere"}
        for event, subject_tpl in DEFAULT_SUBJECTS.items():
            with self.subTest(event=event):
                subject, text, html = render_email_bodies(
                    subject_tpl, DEFAULT_TEXT_BODIES[event], DEFAULT_HTML_BODIES[event], self._config(), ctx,
                )
                self.assertNotIn("{{", subject + text + html)
                self.assertNotIn("{%", html)
                self.assertIn("#e84a7a", html)  # legacy indigo replaced by site primary
                self.assertNotIn("#6366f1", html)
                self.assertNotIn("SajiloWork", html)

    def test_custom_primary_color_is_respected(self):
        from email_service.defaults import DEFAULT_HTML_BODIES, DEFAULT_SUBJECTS, DEFAULT_TEXT_BODIES

        e = EmailEvent.LOGIN_VERIFICATION
        _, _, html = render_email_bodies(
            DEFAULT_SUBJECTS[e], DEFAULT_TEXT_BODIES[e], DEFAULT_HTML_BODIES[e],
            self._config(color="#123456"), {"otp_code": "1", "expiry_minutes": 10},
        )
        self.assertIn("#123456", html)

    def test_previous_shipped_html_is_upgraded(self):
        from email_service.defaults import TEMPLATE_VERSION, ensure_default_templates
        from email_service.models import EmailTemplate

        ensure_default_templates()
        EmailTemplate.objects.filter(event=EmailEvent.WELCOME).update(html_body="<!-- duo-template:v1 --><p>old</p>")
        ensure_default_templates()
        self.assertIn(TEMPLATE_VERSION, EmailTemplate.objects.get(event=EmailEvent.WELCOME).html_body)

    def test_fragment_html_message_gets_branded_wrapper(self):
        from unittest import mock
        from email_service import service

        captured = {}

        def fake_deliver(config, *, to, subject, text_body, html_body):
            captured["html"] = html_body
            return service.DeliveryResult(True, "smtp", message_id="x")

        with mock.patch.object(service, "_deliver", fake_deliver):
            service.send_email(to="a@example.com", subject="Hi", message="t", html_message="<p>frag</p>")
        self.assertIn("<!DOCTYPE html>", captured["html"])
        self.assertIn("<p>frag</p>", captured["html"])
