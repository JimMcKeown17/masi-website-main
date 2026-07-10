import html as html_lib
import json
import os
import re
from pathlib import Path

import anthropic

from fundraising.services.email_template import render_email


MODEL = "claude-sonnet-5"
_INLINE_IMG_STYLE = ("display:block;width:100%;max-width:600px;height:auto;"
                     "margin:12px auto;border-radius:8px;")
VOICE_GUIDE_PATH = Path(__file__).resolve().parents[1] / "voice" / "voice_guide.md"
STRUCTURE_DIR = VOICE_GUIDE_PATH.parent
CONTRACT = (
    "Mechanical contract:\n"
    '- Write the BODY html of the email only; return only a JSON object with keys "subject" and "html".\n'
    "- Never include logo, donate button, social links, or the lead story's photo; the template adds those around the body.\n"
    '- For each story whose "is_lead" is false AND "hero_image_url" is set, embed that photo inline under its paragraph as: '
    f'<img src="THE_URL" alt="" width="600" style="{_INLINE_IMG_STYLE}">. Never embed the is_lead story\'s photo.\n'
    '- If a "chart" object is provided, you MAY embed it exactly once, in the broadening section, as:\n'
    f'<img src="IMAGE_URL" alt="ALT" width="600" style="{_INLINE_IMG_STYLE}">\n'
    '<p style="font-size:13px;color:#6b7482;text-align:center;margin:4px 0 16px;">CAPTION</p>\n'
    "Use the exact caption text; never restyle or rewrite it. Whether to include it is governed by the structure file.\n"
    "- Where the structure file calls for the mid-email ask, emit exactly <!--MID_CTA--> on its own line; the template replaces it with the donate button."
)


class VoiceGuide:
    def read(self):
        return VOICE_GUIDE_PATH.read_text(encoding="utf-8")


voice_guide = VoiceGuide()


def _load_structure(name):
    return (STRUCTURE_DIR / f"structure-{name}.md").read_text(encoding="utf-8")


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


def _system_prompt(guide_text, structure_text):
    return f"{guide_text}\n\n{structure_text}\n\n{CONTRACT}"


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
    # Models sometimes wrap the JSON in a markdown code fence; strip it first.
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = re.sub(r'^```[a-zA-Z]*\s*', '', raw_text)
        raw_text = re.sub(r'\s*```$', '', raw_text)
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


def compose_newsletter(
    stories,
    stat,
    voice_guide,
    cta_text=None,
    cta_url=None,
    structure="story",
    chart=None,
):
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is required")

    guide_text = voice_guide.read() if hasattr(voice_guide, 'read') else str(voice_guide)
    system_prompt = _system_prompt(guide_text, _load_structure(structure))

    lead_index = next((i for i, s in enumerate(stories) if getattr(s, "hero_image_url", "")), None)
    lead_url = stories[lead_index].hero_image_url if lead_index is not None else ""
    stats = stat if isinstance(stat, list) else ([] if stat is None else [stat])
    payload = {
        "stories": [_story_payload(s, is_lead=(i == lead_index)) for i, s in enumerate(stories)],
        "stats": [_stat_payload(item) for item in stats],
    }
    if chart is not None:
        payload["chart"] = {
            "image_url": chart["image_url"],
            "caption": chart["caption"],
            "alt": chart["alt"],
        }
    user_content = json.dumps(payload, default=str)

    client = anthropic.Anthropic(api_key=api_key)
    # Thinking tokens count toward max_tokens; 2500 truncated a real run (Draft 7).
    response = client.messages.create(
        model=MODEL,
        max_tokens=6000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    if response.stop_reason != "end_turn":
        print(f"[compose_newsletter] stop_reason={response.stop_reason} "
              f"output_tokens={response.usage.output_tokens}")
    parsed = _parse_json_result(_response_text(response))
    body_html = parsed["html"]

    missing = _missing_inline_images(body_html, stories, lead_url)
    if missing:
        print(f"[compose_newsletter] model dropped {len(missing)} inline image(s): {missing}")

    return {
        "subject": parsed["subject"],
        "html": render_email(body_html, lead_url, cta_text, cta_url),
    }
