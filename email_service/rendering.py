"""HTML email rendering with branding."""

from __future__ import annotations

import html
import re
from typing import Any

from django.template import Context, Template
from django.utils.html import strip_tags

from email_service.config import EmailConfig

_VAR_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def _sanitize_context(context: dict[str, Any]) -> dict[str, str]:
    safe: dict[str, str] = {}
    for key, value in context.items():
        if value is None:
            safe[key] = ""
        elif isinstance(value, (int, float, bool)):
            safe[key] = str(value)
        else:
            safe[key] = html.escape(str(value))
    return safe


def render_template_string(template_str: str, context: dict[str, Any]) -> str:
    if not template_str:
        return ""
    try:
        return Template(template_str).render(Context(context))
    except Exception:
        rendered = template_str
        for key, value in context.items():
            rendered = rendered.replace(f"{{{{ {key} }}}}", str(value))
            rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
        return rendered


def build_branding_context(config: EmailConfig, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = {
        "brand_name": config.from_name or "SajiloWork",
        "brand_logo_url": config.brand_logo_url,
        "brand_primary_color": config.brand_primary_color or "#6366f1",
        "footer_text": config.footer_text,
        "social_links": config.social_links,
        "from_email": config.from_email,
    }
    if extra:
        ctx.update(extra)
    return ctx


def wrap_html_body(inner_html: str, config: EmailConfig, preview_title: str = "") -> str:
    logo = config.brand_logo_url
    color = config.brand_primary_color or "#6366f1"
    brand = html.escape(config.from_name or "SajiloWork")
    footer = html.escape(config.footer_text or "")
    logo_block = (
        f'<img src="{html.escape(logo)}" alt="{brand}" width="120" '
        'style="max-width:120px;height:auto;margin-bottom:16px;" />'
        if logo
        else f'<div style="font-size:22px;font-weight:700;color:{color};">{brand}</div>'
    )
    title = html.escape(preview_title) if preview_title else brand
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f4f5;padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.06);">
          <tr>
            <td style="padding:32px 32px 16px;text-align:center;border-bottom:3px solid {color};">
              {logo_block}
            </td>
          </tr>
          <tr>
            <td style="padding:32px;color:#18181b;font-size:16px;line-height:1.6;">
              {inner_html}
            </td>
          </tr>
          <tr>
            <td style="padding:24px 32px;background:#fafafa;color:#71717a;font-size:13px;text-align:center;border-top:1px solid #e4e4e7;">
              {footer}
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def text_to_html_paragraphs(text: str) -> str:
    paragraphs = [html.escape(p.strip()) for p in text.split("\n\n") if p.strip()]
    return "".join(f"<p style='margin:0 0 16px;'>{p.replace(chr(10), '<br/>')}</p>" for p in paragraphs)


def render_email_bodies(
    subject_tpl: str,
    text_tpl: str,
    html_tpl: str,
    config: EmailConfig,
    context: dict[str, Any],
) -> tuple[str, str, str]:
    branding = build_branding_context(config, context)
    subject = render_template_string(subject_tpl, branding)
    text_body = render_template_string(text_tpl, branding)
    if html_tpl.strip():
        inner = render_template_string(html_tpl, branding)
    else:
        inner = text_to_html_paragraphs(strip_tags(text_body))
    html_body = wrap_html_body(inner, config, preview_title=subject)
    return subject, text_body, html_body


def preview_email(
    event: str,
    config: EmailConfig,
    subject_tpl: str,
    text_tpl: str,
    html_tpl: str,
    sample_context: dict[str, Any] | None = None,
) -> dict[str, str]:
    sample = {
        "otp_code": "123456",
        "expiry_minutes": "10",
        "user_name": "Alex",
        "message": "This is a preview of your email template.",
        **(sample_context or {}),
    }
    subject, text_body, html_body = render_email_bodies(
        subject_tpl, text_tpl, html_tpl, config, sample
    )
    return {"subject": subject, "text_body": text_body, "html_body": html_body}
