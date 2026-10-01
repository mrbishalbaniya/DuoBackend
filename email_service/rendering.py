"""HTML email rendering with Duo branding.

The look mirrors the website theme (DuoFrontend/app/globals.css): dark
surfaces, rose primary ``#e84a7a``, the rose → love → gold brand gradient,
Plus Jakarta Sans headings and Inter body text.

Everything is tables + inline styles so it survives Gmail, Outlook and
Apple Mail. Web fonts load where supported and fall back to system fonts.
"""

from __future__ import annotations

import html
import re
from datetime import date
from typing import Any

from django.conf import settings
from django.template import Context, Template
from django.utils.html import strip_tags

from email_service.config import EmailConfig

_VAR_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")

# ── Theme tokens (keep in sync with DuoFrontend/app/globals.css) ──────────
THEME = {
    "background": "#0f0f10",
    "surface": "#17181a",
    "surface_high": "#202225",
    "surface_lowest": "#0f0f10",
    "border": "#2f3136",
    "text": "#ffffff",
    "text_muted": "#b0b3ba",
    "text_subtle": "#9ca3af",
    "primary": "#e84a7a",
    "primary_soft": "#2a161e",
    "love": "#ff4d6d",
    "accent": "#d4a574",
    "error": "#ef4444",
    "gradient": "linear-gradient(135deg,#e84a7a 0%,#ff4d6d 50%,#d4a574 100%)",
    "font_heading": "'Plus Jakarta Sans','Segoe UI',Roboto,Helvetica,Arial,sans-serif",
    "font_body": "Inter,'Segoe UI',Roboto,Helvetica,Arial,sans-serif",
    "font_mono": "Consolas,Menlo,'Courier New',monospace",
}

# Colours that shipped as defaults before the site theme existed. When the
# admin never changed them we use the site theme instead.
LEGACY_PRIMARY_COLORS = {"", "#6366f1"}
LEGACY_FOOTER_TEXTS = {"", "© SajiloWork. All rights reserved."}


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


def brand_name(config: EmailConfig) -> str:
    return (config.from_name or "Duo").strip()


def primary_color(config: EmailConfig) -> str:
    color = (config.brand_primary_color or "").strip().lower()
    return THEME["primary"] if color in LEGACY_PRIMARY_COLORS else config.brand_primary_color.strip()


def footer_text(config: EmailConfig) -> str:
    text = (config.footer_text or "").strip()
    if text in LEGACY_FOOTER_TEXTS or "sajilowork" in text.lower():
        return f"© {date.today().year} {brand_name(config)}. All rights reserved."
    return text


def site_url() -> str:
    return (getattr(settings, "FRONTEND_URL", "") or "").rstrip("/")


def _social_links(config: EmailConfig) -> list[tuple[str, str]]:
    links = []
    for line in (config.social_links or "").splitlines():
        if "|" not in line:
            continue
        label, url = (part.strip() for part in line.split("|", 1))
        if label and url.startswith(("http://", "https://")):
            links.append((label, url))
    return links


def build_branding_context(config: EmailConfig, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = {
        "brand_name": brand_name(config),
        "brand_logo_url": config.brand_logo_url,
        "brand_primary_color": primary_color(config),
        "footer_text": footer_text(config),
        "social_links": config.social_links,
        "from_email": config.from_email,
        "site_url": site_url(),
    }
    if extra:
        ctx.update(extra)
    return ctx


# ── Reusable building blocks for template bodies ─────────────────────────
def button_html(label: str, href: str, color: str = "{{ brand_primary_color }}") -> str:
    """Bulletproof pill button (works without CSS support for <a> padding)."""
    return (
        '<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:0 auto;">'
        f'<tr><td align="center" bgcolor="{color}" style="border-radius:999px;background:{color};">'
        f'<a href="{href}" target="_blank" style="display:inline-block;padding:15px 34px;'
        f"font-family:{THEME['font_heading']};font-size:15px;font-weight:700;line-height:20px;"
        f'color:#ffffff;text-decoration:none;border-radius:999px;">{label}</a>'
        "</td></tr></table>"
    )


def _logo_block(config: EmailConfig, color: str) -> str:
    name = html.escape(brand_name(config))
    if config.brand_logo_url:
        return (
            f'<img src="{html.escape(config.brand_logo_url)}" alt="{name}" width="56" height="56" '
            'style="display:block;width:56px;height:56px;border:0;border-radius:16px;margin:0 auto;" />'
        )
    # Pure-HTML version of the app icon: gradient rounded square with a heart.
    return (
        '<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:0 auto;">'
        "<tr>"
        f'<td align="center" valign="middle" width="44" height="44" bgcolor="{color}" '
        f'style="width:44px;height:44px;border-radius:14px;background:{color};'
        f"background-image:{THEME['gradient']};color:#ffffff;font-size:22px;line-height:44px;"
        f"font-family:Arial,sans-serif;\">&#9829;&#xFE0E;</td>"
        f'<td style="padding-left:12px;font-family:{THEME["font_heading"]};font-size:24px;'
        f'font-weight:800;letter-spacing:-0.5px;color:{THEME["text"]};">{name}</td>'
        "</tr></table>"
    )


def wrap_html_body(
    inner_html: str, config: EmailConfig, preview_title: str = "", preheader: str = ""
) -> str:
    t = THEME
    color = primary_color(config)
    brand = html.escape(brand_name(config))
    footer = html.escape(footer_text(config))
    title = html.escape(preview_title) if preview_title else brand
    url = site_url()

    preheader_block = (
        '<div style="display:none;font-size:1px;line-height:1px;max-height:0px;max-width:0px;'
        f'opacity:0;overflow:hidden;color:{t["background"]};">{html.escape(preheader)}</div>'
        if preheader
        else ""
    )

    links = _social_links(config)
    if url:
        links = [("Open " + brand_name(config), url), ("Help", f"{url}/help"), *links]
    links_html = " &nbsp;·&nbsp; ".join(
        f'<a href="{html.escape(href)}" target="_blank" style="color:{t["text_muted"]};'
        f'text-decoration:underline;">{html.escape(label)}</a>'
        for label, href in links
    )
    links_row = (
        f'<tr><td align="center" style="padding:0 0 10px;font-size:13px;line-height:20px;">{links_html}</td></tr>'
        if links_html
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="dark light" />
  <meta name="supported-color-schemes" content="dark light" />
  <title>{title}</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&amp;family=Plus+Jakarta+Sans:wght@600;700;800&amp;display=swap" rel="stylesheet" />
</head>
<body bgcolor="{t['background']}" style="margin:0;padding:0;background:{t['background']};font-family:{t['font_body']};-webkit-font-smoothing:antialiased;">
  {preheader_block}
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="{t['background']}" style="background:{t['background']};">
    <tr>
      <td align="center" style="padding:36px 16px 40px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;">
          <tr>
            <td align="center" style="padding:0 0 22px;">{_logo_block(config, color)}</td>
          </tr>
          <tr>
            <td bgcolor="{t['surface']}" style="background:{t['surface']};border:1px solid {t['border']};border-radius:24px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td style="padding:36px 36px 36px;color:{t['text']};font-family:{t['font_body']};font-size:16px;line-height:26px;">
                    {inner_html}
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding:28px 16px 0;font-family:{t['font_body']};color:{t['text_subtle']};">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td align="center" style="padding:0 0 12px;font-family:{t['font_heading']};font-size:11px;font-weight:700;letter-spacing:3px;color:{t['accent']};">CONNECT &middot; MATCH &middot; LOVE</td>
                </tr>
                {links_row}
                <tr>
                  <td align="center" style="font-size:12px;line-height:18px;color:{t['text_subtle']};">
                    You're receiving this email because of activity on your {brand} account.<br />
                    {footer}
                  </td>
                </tr>
              </table>
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
    return "".join(
        f"<p style='margin:0 0 16px;color:{THEME['text_muted']};'>{p.replace(chr(10), '<br/>')}</p>"
        for p in paragraphs
    )


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
    preheader = ""
    if branding.get("otp_code"):
        preheader = (
            f"Your code is {branding['otp_code']}. "
            f"It expires in {branding.get('expiry_minutes', 10)} minutes."
        )
    elif branding.get("preheader"):
        preheader = str(branding["preheader"])
    html_body = wrap_html_body(inner, config, preview_title=subject, preheader=preheader)
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
