"""Deterministic email chrome around the model-written newsletter body:
Masi logo header + lead hero photo + body + donate CTA + social footer.
Keeping the chrome in code (not the model) makes the logo/CTA/socials reliable
and email-safe; the model only writes the story body."""

LOGO_URL = "https://storage.googleapis.com/masi-website/fundraising/assets/masi-logo.png"

# Masi's real accounts (from the site footer). Add X here if one exists.
SOCIAL_LINKS = [
    ("Facebook", "https://www.facebook.com/masinyusane/"),
    ("Instagram", "https://www.instagram.com/masinyusane/"),
    ("TikTok", "https://www.tiktok.com/@masinyusane1"),
    ("Website", "https://masinyusane.org"),
]

DEFAULT_CTA_TEXT = "Donate"
DEFAULT_CTA_URL = "https://masinyusane.org/donate"

_RED = "#e4002b"  # Masi brand red (button); tweak on the rendered draft


def _lead_hero(lead_hero_url):
    if not lead_hero_url:
        return ""
    return (
        f'<img src="{lead_hero_url}" alt="" width="600" '
        'style="display:block;width:100%;max-width:600px;height:auto;'
        'margin:16px auto;border-radius:8px;">'
    )


def _cta(cta_text, cta_url):
    return (
        '<div style="text-align:center;margin:28px 0;">'
        f'<a href="{cta_url}" style="background:{_RED};color:#ffffff;'
        'text-decoration:none;padding:14px 30px;border-radius:8px;'
        f'font-weight:bold;display:inline-block;font-size:16px;">{cta_text}</a></div>'
    )


def _social_footer():
    links = " &nbsp;&middot;&nbsp; ".join(
        f'<a href="{url}" style="color:#6b7482;text-decoration:none;">{name}</a>'
        for name, url in SOCIAL_LINKS
    )
    return (
        '<div style="text-align:center;font-size:13px;color:#6b7482;'
        'padding:22px 0 8px;border-top:1px solid #e4e7ec;margin-top:28px;">'
        f'{links}</div>'
    )


def render_email(body_html, lead_hero_url, cta_text=None, cta_url=None):
    """Wrap the model-written body in the fixed Masi newsletter chrome and
    return a full, email-safe HTML document."""
    cta_text = cta_text or DEFAULT_CTA_TEXT
    cta_url = cta_url or DEFAULT_CTA_URL
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;color:#14181f;'
        'line-height:1.5;max-width:640px;margin:0 auto;padding:0 16px;">'
        '<div style="text-align:center;font-size:12px;color:#9aa3b0;padding:8px 0;">'
        '<a href="*|ARCHIVE|*" style="color:#9aa3b0;">View this email in your browser</a></div>'
        f'<img src="{LOGO_URL}" alt="Masinyusane" width="200" '
        'style="display:block;margin:6px auto 0;max-width:200px;height:auto;">'
        f'{_lead_hero(lead_hero_url)}'
        f'<div>{body_html}</div>'
        f'{_cta(cta_text, cta_url)}'
        f'{_social_footer()}'
        '</div>'
    )
