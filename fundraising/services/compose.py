import html as html_lib
import json
import os
import re
from pathlib import Path

import anthropic


MODEL = "claude-sonnet-5"
VOICE_GUIDE_PATH = Path(__file__).resolve().parents[1] / "voice" / "voice_guide.md"


class VoiceGuide:
    def read(self):
        return VOICE_GUIDE_PATH.read_text(encoding="utf-8")


voice_guide = VoiceGuide()


def _story_payload(story):
    return {
        "headline": story.headline,
        "title": story.title,
        "narrative": story.narrative,
        "quote": story.quote,
        "feature_name": story.feature_name,
        "school": story.school,
        "category": story.category,
    }


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


def compose_newsletter(stories, stat, voice_guide):
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is required")

    guide_text = voice_guide.read() if hasattr(voice_guide, 'read') else str(voice_guide)
    system_prompt = (
        f"{guide_text}\n\n"
        "Hard rules:\n"
        "- Write a warm, donor-facing Masinyusane newsletter issue in this voice.\n"
        "- Use ONLY the facts in the provided stories and the single provided stat.\n"
        "- Never invent numbers, names, or outcomes.\n"
        "- Output clean inline-styled HTML suitable for an email.\n"
        "- Use short paragraphs, a headline per story, and the coach quote as a blockquote.\n"
        "- End with a brief thank-you to donors.\n"
        "- Return only a JSON object with keys \"subject\" and \"html\"."
    )
    user_content = json.dumps(
        {
            "stories": [_story_payload(story) for story in stories],
            "stat": _stat_payload(stat),
        },
        default=str,
    )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=2500,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": user_content,
            }
        ],
    )
    return _parse_json_result(_response_text(response))
