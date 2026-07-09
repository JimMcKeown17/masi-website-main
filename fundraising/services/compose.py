import html as html_lib
import json
import os
import re
from pathlib import Path

import anthropic

from fundraising.services.email_template import render_email


MODEL = "claude-sonnet-5"
_INLINE_IMG_STYLE = ("display:block;width:100%;max-width:560px;height:auto;"
                     "margin:12px 0;border-radius:8px;")
VOICE_GUIDE_PATH = Path(__file__).resolve().parents[1] / "voice" / "voice_guide.md"


class VoiceGuide:
    def read(self):
        return VOICE_GUIDE_PATH.read_text(encoding="utf-8")


voice_guide = VoiceGuide()


def _story_payload(story, is_lead=False):
    return {
        "headline": story.headline,
        "title": story.title,
        "narrative": story.narrative,
        "quote": story.quote,
        "feature_name": story.feature_name,
        "school": story.school,
        "category": story.category,
        "hero_image_url": story.hero_image_url,
        "is_lead": is_lead,
    }


def _lead_hero_url(stories):
    """The lead photo shown as the header = the first story that has a hero."""
    for story in stories:
        if getattr(story, "hero_image_url", ""):
            return story.hero_image_url
    return ""


def _missing_inline_images(html, stories, lead_url):
    """Non-lead story photos the model was asked to embed but didn't (validation)."""
    expected = [s.hero_image_url for s in stories
                if getattr(s, "hero_image_url", "") and s.hero_image_url != lead_url]
    return [url for url in expected if url not in html]


def _system_prompt(guide_text):
    return (
        f"{guide_text}\n\n"
        "Write the BODY of a warm, donor-facing Masinyusane newsletter in this voice.\n"
        "Hard rules:\n"
        "- Use ONLY the facts in the provided stories and the single provided stat; never invent numbers, names, or outcomes.\n"
        "- Refer to every child or youth by FIRST NAME ONLY. Never use a surname or last name, even if the source text includes one.\n"
        "- Never use an em dash; never use an emoji.\n"
        "- Output clean inline-styled HTML for the BODY only: a greeting, one section per story (headline, short paragraphs, the coach quote as a blockquote), a brief donate ask, and a thank-you close with a monthly-donor P.S.\n"
        "- Do NOT add a logo, a donate button, social links, or the lead story's photo; those are added around your body automatically.\n"
        f'- For each story whose "is_lead" is false AND "hero_image_url" is set, embed that photo INLINE under its headline as: <img src="THE_URL" alt="" width="600" style="{_INLINE_IMG_STYLE}">. Do NOT embed the is_lead story\'s photo.\n'
        '- Return only a JSON object with keys "subject" and "html".'
    )


def _stat_payload(stat):
    if stat is None:
        return None
    return {
        "value": stat.value,
        "label": stat.label,
        "source_system": stat.source_system,
        "as_of": stat.as_of.isoformat() if stat.as_of else None,
    }


def _response_text(response):
    parts = []
    for block in getattr(response, 'content', []):
        text = getattr(block, 'text', None)
        if text:
            parts.append(text)
        elif isinstance(block, str):
            parts.append(block)
    return "\n".join(parts).strip()


def _derive_subject(raw_text):
    for line in raw_text.splitlines():
        cleaned = re.sub(r'<[^>]+>', '', line).strip()
        if cleaned:
            return cleaned[:80]
    return "Masinyusane update"


def _fallback_result(raw_text):
    escaped = html_lib.escape(raw_text or "")
    html = escaped.replace("\n", "<br>")
    return {
        "subject": _derive_subject(raw_text),
        "html": f'<div style="font-family: Arial, sans-serif; line-height: 1.5;">{html}</div>',
    }


def _parse_json_result(raw_text):
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find('{')
        end = raw_text.rfind('}')
        if start == -1 or end == -1 or end <= start:
            return _fallback_result(raw_text)
        try:
            payload = json.loads(raw_text[start:end + 1])
        except json.JSONDecodeError:
            return _fallback_result(raw_text)

    if not isinstance(payload, dict):
        return _fallback_result(raw_text)
    subject = payload.get('subject')
    html = payload.get('html')
    if not subject or not html:
        return _fallback_result(raw_text)
    return {"subject": str(subject), "html": str(html)}


def compose_newsletter(stories, stat, voice_guide, cta_text=None, cta_url=None):
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is required")

    guide_text = voice_guide.read() if hasattr(voice_guide, 'read') else str(voice_guide)
    system_prompt = _system_prompt(guide_text)

    lead_index = next((i for i, s in enumerate(stories) if getattr(s, "hero_image_url", "")), None)
    lead_url = stories[lead_index].hero_image_url if lead_index is not None else ""
    user_content = json.dumps(
        {
            "stories": [_story_payload(s, is_lead=(i == lead_index)) for i, s in enumerate(stories)],
            "stat": _stat_payload(stat),
        },
        default=str,
    )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=2500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    parsed = _parse_json_result(_response_text(response))
    body_html = parsed["html"]

    missing = _missing_inline_images(body_html, stories, lead_url)
    if missing:
        print(f"[compose_newsletter] model dropped {len(missing)} inline image(s): {missing}")

    return {
        "subject": parsed["subject"],
        "html": render_email(body_html, lead_url, cta_text, cta_url),
    }
