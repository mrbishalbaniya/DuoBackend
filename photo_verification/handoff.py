"""Cross-device verification handoff helpers."""

from __future__ import annotations

from django.conf import settings

from email_service.constants import EmailEvent
from email_service.service import send_email


def build_handoff_url(session_token) -> str:
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/verify/device?session={session_token}"


def send_verification_handoff_email(*, to: str, handoff_url: str, user_name: str = "") -> None:
    greeting = f"Hi {user_name}," if user_name else "Hi,"
    text = (
        f"{greeting}\n\n"
        "Continue your Duo profile verification on this device. "
        "Open the link below on your phone or tablet — no login required.\n\n"
        f"{handoff_url}\n\n"
        "This link expires in 30 minutes. If you did not request verification, you can ignore this email."
    )
    html = f"""
<p style="margin:0 0 16px;">{greeting}</p>
<p style="margin:0 0 16px;">
  Continue your Duo profile verification on this device. Tap the button below on your phone or tablet.
  No login is required — the link is all you need.
</p>
<p style="margin:0 0 24px;text-align:center;">
  <a href="{handoff_url}"
     style="display:inline-block;padding:14px 28px;background:#6366f1;color:#ffffff;text-decoration:none;border-radius:10px;font-weight:600;">
    Open verification
  </a>
</p>
<p style="margin:0;font-size:14px;color:#71717a;">
  Or copy this link: <a href="{handoff_url}">{handoff_url}</a><br/>
  This link expires in 30 minutes.
</p>
"""
    send_email(
        event=EmailEvent.GENERIC,
        to=to,
        subject="Complete your Duo profile verification",
        message=text,
        html_message=html,
        fail_silently=False,
    )
