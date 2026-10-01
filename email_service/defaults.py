"""Default email templates and event settings.

HTML bodies are styled to match the website theme (see ``rendering.THEME``)
and are placed inside ``rendering.wrap_html_body`` which adds the logo
header, gradient card and footer.
"""

from __future__ import annotations

from email_service.constants import EmailEvent
from email_service.models import EmailEventSetting, EmailTemplate
from email_service.rendering import THEME, button_html

# Bump when the shipped HTML changes; stored rows carrying an older marker
# (i.e. never hand-edited in admin) are upgraded automatically.
TEMPLATE_VERSION = "duo-template:v7"
_MARKER = f"<!-- {TEMPLATE_VERSION} -->"

DEFAULT_SUBJECTS = {
    EmailEvent.REGISTRATION_OTP: "{{ otp_code }} is your {{ brand_name }} verification code",
    EmailEvent.PASSWORD_RESET_OTP: "{{ otp_code }} is your {{ brand_name }} password reset code",
    EmailEvent.WELCOME: "Welcome to {{ brand_name }}",
    EmailEvent.LOGIN_VERIFICATION: "{{ otp_code }} is your {{ brand_name }} login code",
    EmailEvent.EMAIL_CHANGE: "{{ otp_code }} is your code to confirm your new {{ brand_name }} email",
    EmailEvent.SUBSCRIPTION_CONFIRMED: "{% if plan_name %}{{ plan_name }} is active{% else %}Payment confirmed{% endif %} — {{ brand_name }}",
    EmailEvent.SUBSCRIPTION_FAILED: "{% if title %}{{ title }}{% else %}Payment didn't go through{% endif %} — {{ brand_name }}",
    EmailEvent.MATCH_NOTIFICATION: "{% if match_name %}You matched with {{ match_name }}{% else %}You have a new match{% endif %} on {{ brand_name }}",
    EmailEvent.ADMIN_ANNOUNCEMENT: "{% if title %}{{ title }}{% else %}News from {{ brand_name }}{% endif %}",
    EmailEvent.CONTACT_FORM: "New contact form message",
    EmailEvent.ACCOUNT_STATUS: "{% if title %}{{ title }}{% else %}Your account status changed{% endif %} — {{ brand_name }}",
    EmailEvent.GENERIC: "{% if title %}{{ title }}{% else %}Message from {{ brand_name }}{% endif %}",
}

# Subjects shipped before the OTP redesign. Stored rows still equal to one of
# these were never customised by an admin and are safe to upgrade.
LEGACY_SUBJECTS = {
    EmailEvent.REGISTRATION_OTP: "{{ brand_name }} verification code",
    EmailEvent.PASSWORD_RESET_OTP: "Reset your {{ brand_name }} password",
    EmailEvent.LOGIN_VERIFICATION: "{{ brand_name }} login verification",
    EmailEvent.EMAIL_CHANGE: "Confirm your new email on {{ brand_name }}",
}

PREVIOUS_SUBJECTS = {
    EmailEvent.SUBSCRIPTION_CONFIRMED: "Payment confirmed — {{ brand_name }}",
    EmailEvent.SUBSCRIPTION_FAILED: "Payment issue — {{ brand_name }}",
    EmailEvent.MATCH_NOTIFICATION: "You have a new match on {{ brand_name }}",
    EmailEvent.ADMIN_ANNOUNCEMENT: "{{ brand_name }} announcement",
    EmailEvent.ACCOUNT_STATUS: "Your {{ brand_name }} account status changed",
    EmailEvent.GENERIC: "Message from {{ brand_name }}",
}

# Signatures of earlier shipped HTML (before version markers existed).
_LEGACY_HTML_SIGNATURES = ("<strong>Keep this code private.</strong>",)

T = THEME


# ── Building blocks ───────────────────────────────────────────────────────
def _eyebrow(text: str, color: str = "{{ brand_primary_color }}") -> str:
    return (
        f'<tr><td style="padding:0 0 10px;font-family:{T["font_heading"]};font-size:12px;'
        f'font-weight:700;letter-spacing:2px;text-transform:uppercase;color:{color};">{text}</td></tr>'
    )


def _heading(text: str) -> str:
    return (
        f'<tr><td style="padding:0 0 14px;font-family:{T["font_heading"]};font-size:26px;'
        f'line-height:34px;font-weight:800;letter-spacing:-0.4px;color:{T["text"]};">{text}</td></tr>'
    )


def _paragraph(text: str, pad: str = "0 0 24px") -> str:
    return (
        f'<tr><td style="padding:{pad};font-size:16px;line-height:26px;color:{T["text_muted"]};">'
        f"{text}</td></tr>"
    )


def _note(text: str, color: str = T["accent"]) -> str:
    return (
        '<tr><td style="padding:0 0 24px;">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>'
        f'<td bgcolor="{T["surface_high"]}" style="padding:14px 16px;background:{T["surface_high"]};'
        f"border-left:3px solid {color};border-radius:12px;font-size:14px;line-height:22px;"
        f'color:{T["text_muted"]};">{text}</td>'
        "</tr></table></td></tr>"
    )


def _cta(label: str, href: str, color: str = "{{ brand_primary_color }}") -> str:
    return f'<tr><td align="center" style="padding:4px 0 28px;">{button_html(label, href, color)}</td></tr>'


def _small(text: str) -> str:
    return f'<tr><td style="font-size:14px;line-height:22px;color:{T["text_subtle"]};">{text}</td></tr>'


def _message_box() -> str:
    return (
        '<tr><td style="padding:0 0 24px;">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>'
        f'<td bgcolor="{T["surface_lowest"]}" style="padding:18px 20px;background:{T["surface_lowest"]};'
        f'border:1px solid {T["border"]};border-radius:16px;font-size:15px;line-height:24px;color:{T["text"]};">'
        "{{ message|linebreaksbr }}</td>"
        "</tr></table></td></tr>"
    )


def _steps(items: list[tuple[str, str]]) -> str:
    rows = "".join(
        "<tr>"
        f'<td valign="top" width="36" style="padding:0 0 16px;">'
        f'<table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr>'
        f'<td align="center" width="26" height="26" bgcolor="{T["primary_soft"]}" '
        f'style="width:26px;height:26px;border-radius:999px;background:{T["primary_soft"]};'
        f'font-family:{T["font_heading"]};font-size:13px;font-weight:700;line-height:26px;'
        f'color:{{{{ brand_primary_color }}}};">{i}</td></tr></table></td>'
        f'<td valign="top" style="padding:2px 0 16px;font-size:15px;line-height:22px;color:{T["text_muted"]};">'
        f'<strong style="color:{T["text"]};font-weight:600;">{title}</strong><br />{desc}</td>'
        "</tr>"
        for i, (title, desc) in enumerate(items, start=1)
    )
    return (
        '<tr><td style="padding:0 0 12px;">'
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">{rows}</table>'
        "</td></tr>"
    )


def _details() -> str:
    """Label/value rows from ``details`` (list of {"label", "value"} dicts)."""
    return (
        "{% if details %}"
        '<tr><td style="padding:0 0 24px;">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
        f'style="border:1px solid {T["border"]};border-radius:16px;border-collapse:separate;">'
        "{% for row in details %}"
        "<tr>"
        f'<td style="padding:12px 18px;font-size:14px;line-height:20px;color:{T["text_subtle"]};'
        "{% if not forloop.last %}"
        f'border-bottom:1px solid {T["border"]};'
        '{% endif %}">{{ row.label }}</td>'
        f'<td align="right" style="padding:12px 18px;font-size:14px;line-height:20px;font-weight:600;'
        f'color:{T["text"]};'
        "{% if not forloop.last %}"
        f'border-bottom:1px solid {T["border"]};'
        '{% endif %}">{{ row.value }}</td>'
        "</tr>"
        "{% endfor %}"
        "</table></td></tr>"
        "{% endif %}"
    )


def _optional_message() -> str:
    return "{% if message %}" + _message_box() + "{% endif %}"


def _optional_note() -> str:
    return "{% if note %}" + _note("{{ note }}") + "{% endif %}"


def _context_cta(default_label: str, default_path: str) -> str:
    return (
        "{% if cta_url %}"
        + _cta("{% if cta_label %}{{ cta_label }}{% else %}Open " + default_label + "{% endif %}", "{{ cta_url }}")
        + "{% else %}"
        + _cta("Open " + default_label, "{{ site_url }}" + default_path)
        + "{% endif %}"
    )


def _details_text() -> str:
    return "{% for row in details %}{{ row.label }}: {{ row.value }}\n{% endfor %}"


def _rich_text(default_intro: str) -> str:
    return (
        "Hi {{ user_name|default:'there' }},\n\n"
        "{% if intro %}{{ intro }}{% else %}" + default_intro + "{% endif %}\n\n"
        + _details_text()
        + "{% if message %}\n{{ message }}\n{% endif %}"
        "{% if note %}\n{{ note }}\n{% endif %}"
        "{% if cta_url %}\n{{ cta_label|default:'Open' }}: {{ cta_url }}\n{% endif %}"
        "\n{{ footer_text }}"
    )


def _card(*rows: str) -> str:
    return (
        f"{_MARKER}\n"
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">'
        + "".join(rows)
        + "</table>"
    )


def _otp_code_box() -> str:
    return (
        '<tr><td align="center" style="padding:4px 0 14px;">'
        '<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:0 auto;"><tr>'
        f'<td align="center" bgcolor="{T["primary_soft"]}" style="padding:20px 32px 20px 44px;'
        f"background:{T['primary_soft']};border:1px solid {{{{ brand_primary_color }}}};border-radius:18px;"
        f"font-family:{T['font_mono']};font-size:38px;line-height:42px;font-weight:700;"
        f'letter-spacing:12px;color:{T["text"]};">{{{{ otp_code }}}}</td>'
        "</tr></table></td></tr>"
        f'<tr><td align="center" style="padding:0 0 28px;font-size:14px;line-height:22px;color:{T["text_subtle"]};">'
        f'Expires in <strong style="color:{T["text"]};">{{{{ expiry_minutes }}}} minutes</strong>'
        " &nbsp;·&nbsp; single use</td></tr>"
    )


def _otp_html(*, eyebrow: str, heading: str, intro: str, closing: str) -> str:
    return _card(
        _eyebrow(eyebrow),
        _heading(heading),
        _paragraph(intro, "0 0 28px"),
        _otp_code_box(),
        _note(
            f'<strong style="color:{T["text"]};">Keep this code to yourself.</strong> '
            "{{ brand_name }} will never call, text or email you asking for it."
        ),
        _small(closing),
    )


def _otp_text(intro: str, closing: str) -> str:
    return (
        "Hi,\n\n"
        f"{intro}\n\n"
        "    {{ otp_code }}\n\n"
        "This code expires in {{ expiry_minutes }} minutes and can only be used once.\n"
        "Never share this code with anyone. {{ brand_name }} staff will never ask for it.\n\n"
        f"{closing}\n\n"
        "{{ footer_text }}"
    )


def _message_text(intro: str = "") -> str:
    lead = f"{intro}\n\n" if intro else ""
    return "Hi,\n\n" + lead + "{{ message }}\n\n{{ footer_text }}"


# ── Text bodies ───────────────────────────────────────────────────────────
DEFAULT_TEXT_BODIES = {
    EmailEvent.REGISTRATION_OTP: _otp_text(
        "Welcome to {{ brand_name }}! Enter this code on the sign-up screen to verify your email and continue creating your account:",
        "If you didn't try to sign up, you can safely ignore this email. No account will be created.",
    ),
    EmailEvent.PASSWORD_RESET_OTP: _otp_text(
        "We received a request to reset your {{ brand_name }} password. Your reset code is:",
        "If you didn't ask to reset your password, ignore this email. Your password will stay the same.",
    ),
    EmailEvent.LOGIN_VERIFICATION: _otp_text(
        "Someone is signing in to your {{ brand_name }} account. Enter this code to continue:",
        "If this wasn't you, you can ignore this email. Nobody can sign in without this code.",
    ),
    EmailEvent.EMAIL_CHANGE: _otp_text(
        "Use this code to confirm this address as the new email for your {{ brand_name }} account:",
        "If you didn't request this change, ignore this email and your account email will stay the same.",
    ),
    EmailEvent.WELCOME: (
        "Hi {{ user_name|default:'there' }},\n\n"
        "Welcome to {{ brand_name }}! We're glad you're here.\n\n"
        "1. Complete your profile so people get to know the real you.\n"
        "2. Verify your photo to earn the verified badge.\n"
        "3. Start discovering people who share your vibe.\n\n"
        "Start discovering: {{ site_url }}/discover\n\n"
        "{{ footer_text }}"
    ),
    EmailEvent.SUBSCRIPTION_CONFIRMED: _rich_text("Your payment went through. Thank you!"),
    EmailEvent.SUBSCRIPTION_FAILED: _rich_text("We couldn't process your latest payment. You haven't been charged."),
    EmailEvent.MATCH_NOTIFICATION: _rich_text(
        "{% if match_name %}You and {{ match_name }} liked each other.{% else %}You have a new match waiting for you.{% endif %}"
    ),
    EmailEvent.ADMIN_ANNOUNCEMENT: _rich_text("Here's an update from {{ brand_name }}."),
    EmailEvent.CONTACT_FORM: "New contact form message:\n\n{{ message }}",
    EmailEvent.ACCOUNT_STATUS: _rich_text("There's an update about your account."),
    EmailEvent.GENERIC: _rich_text(""),
}

# Text bodies that shipped earlier; rows still equal to these get upgraded.
_LEGACY_TEXT_BODIES = {
    _message_text("Your payment went through. Thank you!"),
    _message_text("We couldn't process your latest payment."),
    _message_text("You have a new match waiting for you."),
    _message_text(),
    _message_text("The status of your account has changed."),
    _otp_text(
        "Use this code to verify your email and finish creating your {{ brand_name }} account:",
        "If you didn't try to sign up, you can safely ignore this email.",
    ),
    "Hi,\n\n{{ message }}\n\n{{ footer_text }}",
    "Hi {{ user_name }},\n\nWelcome to {{ brand_name }}! We're glad you're here.\n\n{{ footer_text }}",
    # Pre-redesign OTP bodies (registration, password reset, login).
    (
        "Hi,\n\nYour verification code is: {{ otp_code }}\n\n"
        "This code expires in {{ expiry_minutes }} minutes.\n\n{{ footer_text }}"
    ),
    (
        "Hi,\n\nYour password reset code is: {{ otp_code }}\n\n"
        "This code expires in {{ expiry_minutes }} minutes.\n"
        "If you did not request this, ignore this email.\n\n{{ footer_text }}"
    ),
    _otp_text(
        "Someone is signing in to your {{ brand_name }} account. Enter this code to continue:",
        "If this wasn't you, change your password right away. Nobody can sign in without this code.",
    ),
}

# ── HTML bodies ───────────────────────────────────────────────────────────
DEFAULT_HTML_BODIES = {
    EmailEvent.REGISTRATION_OTP: _card(
        _eyebrow("Verify your email"),
        _heading("Welcome to {{ brand_name }} 💕"),
        _paragraph(
            "You're one step away from creating your account. "
            "Enter this code on the sign-up screen to confirm this email is yours.",
            "0 0 28px",
        ),
        _otp_code_box(),
        _steps(
            [
                ("Enter the code", "Type the 6 digits on the verification screen."),
                ("Build your profile", "Add your details, location and best photos."),
                ("Start matching", "Meet people nearby who share your vibe."),
            ]
        ),
        _note(
            f'<strong style="color:{T["text"]};">Keep this code to yourself.</strong> '
            "{{ brand_name }} will never call, text or email you asking for it."
        ),
        _small("Didn't try to sign up? You can safely ignore this email. No account will be created."),
    ),
    EmailEvent.PASSWORD_RESET_OTP: _otp_html(
        eyebrow="Password reset",
        heading="Reset your password",
        intro=(
            "We received a request to reset the password for your {{ brand_name }} account. "
            "Enter this code to choose a new one."
        ),
        closing="Didn't ask for a reset? Ignore this email and your password will stay the same.",
    ),
    EmailEvent.LOGIN_VERIFICATION: _otp_html(
        eyebrow="Login verification",
        heading="Confirm it's you",
        intro="Someone is signing in to your {{ brand_name }} account. Enter this code to continue.",
        closing="Wasn't you? You can ignore this email. Nobody can sign in without this code.",
    ),
    EmailEvent.EMAIL_CHANGE: _otp_html(
        eyebrow="Email change",
        heading="Confirm your new email",
        intro="Enter this code to make this address the new email for your {{ brand_name }} account.",
        closing="Didn't request this change? Ignore this email and your account email will stay the same.",
    ),
    EmailEvent.WELCOME: _card(
        _eyebrow("Welcome"),
        _heading("Hi {{ user_name|default:'there' }}, welcome to {{ brand_name }}"),
        _paragraph("We're so glad you're here. Here's how to get the most out of your first few days."),
        _steps(
            [
                ("Complete your profile", "Add photos and a bio so people get to know the real you."),
                ("Verify your photo", "Earn the verified badge and build trust with your matches."),
                ("Start discovering", "Find people nearby who share your vibe."),
            ]
        ),
        _cta("Start discovering", "{{ site_url }}/discover"),
        _small("Need a hand? Our help center is always open."),
    ),
    EmailEvent.SUBSCRIPTION_CONFIRMED: _card(
        _eyebrow("Payment confirmed", T["accent"]),
        _heading("{% if title %}{{ title }}{% else %}You're all set{% endif %}"),
        _paragraph("{% if intro %}{{ intro }}{% else %}Thank you! Your payment went through and your perks are active.{% endif %}"),
        _details(),
        _optional_message(),
        _context_cta("my wallet", "/wallet"),
        _small("Keep this email as your receipt."),
    ),
    EmailEvent.SUBSCRIPTION_FAILED: _card(
        _eyebrow("Payment issue", T["error"]),
        _heading("{% if title %}{{ title }}{% else %}Your payment didn't go through{% endif %}"),
        _paragraph("{% if intro %}{{ intro }}{% else %}We couldn't process your latest payment. You haven't been charged.{% endif %}"),
        _details(),
        _optional_message(),
        _context_cta("my wallet", "/wallet"),
        _small("Questions about this payment? Our help center can sort it out."),
    ),
    EmailEvent.MATCH_NOTIFICATION: _card(
        _eyebrow("New match", T["love"]),
        _heading("{% if match_name %}You matched with {{ match_name }}!{% else %}It's a match!{% endif %}"),
        _paragraph("{% if intro %}{{ intro }}{% else %}You both liked each other. Don't keep them waiting.{% endif %}"),
        _optional_message(),
        _context_cta("chat", "/chat"),
    ),
    EmailEvent.ADMIN_ANNOUNCEMENT: _card(
        _eyebrow("Announcement"),
        _heading("{% if title %}{{ title }}{% else %}News from {{ brand_name }}{% endif %}"),
        _paragraph("{{ message|linebreaksbr }}", "0 0 28px"),
        _context_cta("{{ brand_name }}", ""),
    ),
    EmailEvent.CONTACT_FORM: _card(
        _eyebrow("Contact form"),
        _heading("New message received"),
        _paragraph("Someone sent a message through the contact form."),
        _message_box(),
    ),
    EmailEvent.ACCOUNT_STATUS: _card(
        _eyebrow("Account update", T["accent"]),
        _heading("{% if title %}{{ title }}{% else %}Your account status changed{% endif %}"),
        _paragraph("{% if intro %}{{ intro }}{% else %}There's an update about your account.{% endif %}"),
        _details(),
        _optional_message(),
        _optional_note(),
        _context_cta("{{ brand_name }}", ""),
        _small("If you think this is a mistake, contact support and we'll take a look."),
    ),
    EmailEvent.GENERIC: _card(
        "{% if title %}" + _heading("{{ title }}") + "{% endif %}",
        "{% if intro %}" + _paragraph("{{ intro }}") + "{% endif %}",
        _details(),
        "{% if message %}" + _paragraph("{{ message|linebreaksbr }}") + "{% endif %}",
        _optional_note(),
        "{% if cta_url %}" + _cta("{{ cta_label|default:'Open' }}", "{{ cta_url }}") + "{% endif %}",
    ),
}

OTP_EVENTS = (
    EmailEvent.REGISTRATION_OTP,
    EmailEvent.PASSWORD_RESET_OTP,
    EmailEvent.LOGIN_VERIFICATION,
    EmailEvent.EMAIL_CHANGE,
)


def _html_is_upgradable(stored: str) -> bool:
    body = (stored or "").strip()
    if not body:
        return True
    if "duo-template:" in body:
        return _MARKER not in body
    return any(sig in body for sig in _LEGACY_HTML_SIGNATURES)


def _upgrade_template(event: str) -> None:
    """Bring stored templates up to the current design.

    Only rows that still hold shipped defaults are touched. Anything an admin
    edited by hand (no version marker, not a known legacy default) is kept.
    Old login/email-change rows had no ``{{ otp_code }}`` at all, so those
    text bodies are always fixed.
    """
    template = EmailTemplate.objects.filter(event=event).first()
    if template is None:
        return
    changed = []
    text_default = DEFAULT_TEXT_BODIES.get(event)
    if text_default:
        missing_code = event in OTP_EVENTS and "otp_code" not in template.text_body
        if missing_code or template.text_body.strip() in _LEGACY_TEXT_BODIES:
            if template.text_body != text_default:
                template.text_body = text_default
                changed.append("text_body")
    html_default = DEFAULT_HTML_BODIES.get(event)
    if html_default and _html_is_upgradable(template.html_body):
        template.html_body = html_default
        changed.append("html_body")
    if template.subject in (LEGACY_SUBJECTS.get(event), PREVIOUS_SUBJECTS.get(event)):
        template.subject = DEFAULT_SUBJECTS[event]
        changed.append("subject")
    if changed:
        template.save(update_fields=[*changed, "updated_at"])

    for old_subject in (LEGACY_SUBJECTS.get(event), PREVIOUS_SUBJECTS.get(event)):
        if old_subject:
            EmailEventSetting.objects.filter(event=event, subject_template=old_subject).update(
                subject_template=DEFAULT_SUBJECTS[event]
            )


def ensure_default_templates() -> None:
    for event, subject in DEFAULT_SUBJECTS.items():
        EmailEventSetting.objects.get_or_create(
            event=event,
            defaults={"enabled": True, "subject_template": subject},
        )
        EmailTemplate.objects.get_or_create(
            event=event,
            defaults={
                "subject": subject,
                "text_body": DEFAULT_TEXT_BODIES.get(event, _message_text()),
                "html_body": DEFAULT_HTML_BODIES.get(event, ""),
            },
        )
        _upgrade_template(event)
