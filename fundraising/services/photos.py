"""Story hero photo curation: Drive read -> vision pick -> GCS cache. See
_plans/fundraising-hero-photos-spec.md and ADR 0008."""
import base64
import io
import json
import os
import re

from googleapiclient.errors import HttpError
from PIL import Image, UnidentifiedImageError

from fundraising.services.compose import MODEL


class DriveAccessError(Exception):
    """The service account cannot read a linked Drive item (404/403)."""


class UnreadableImage(Exception):
    """Pillow could not decode a candidate image (e.g. HEIC)."""


_FOLDER_RE = re.compile(r"/folders/([A-Za-z0-9_-]+)")
_FILE_RE = re.compile(r"/file/d/([A-Za-z0-9_-]+)")
_ID_QUERY_RE = re.compile(r"[?&]id=([A-Za-z0-9_-]+)")


def parse_drive_ref(url):
    """Return ("folder"|"file", id) or (None, None). Search URLs and empties
    are unaddressable -> (None, None)."""
    u = (url or "").strip()
    if not u:
        return (None, None)
    m = _FOLDER_RE.search(u)
    if m:
        return ("folder", m.group(1))
    m = _FILE_RE.search(u) or _ID_QUERY_RE.search(u)
    if m:
        return ("file", m.group(1))
    return (None, None)


_FOLDER_MIME = "application/vnd.google-apps.folder"
_MAX_CANDIDATES = 15


def _list_children(drive, parent_id):
    req = drive.files().list(
        q=f"'{parent_id}' in parents and trashed=false",
        fields="files(id,name,mimeType)",
        pageSize=200,
    )
    return req.execute().get("files", [])


def _images(files):
    return [f for f in files if f.get("mimeType", "").startswith("image/")]


def list_candidate_images(drive, kind, ref_id):
    """Return up to _MAX_CANDIDATES image file dicts for a folder or file ref.
    Raises DriveAccessError on a 404/403 (link not shared / deleted)."""
    try:
        if kind == "file":
            meta = drive.files().get(
                fileId=ref_id, fields="id,name,mimeType"
            ).execute()
            return [meta] if meta.get("mimeType", "").startswith("image/") else []

        children = _list_children(drive, ref_id)
        imgs = _images(children)
        if not imgs:
            for sub in [c for c in children if c.get("mimeType") == _FOLDER_MIME]:
                imgs.extend(_images(_list_children(drive, sub["id"])))
                if len(imgs) >= _MAX_CANDIDATES:
                    break
        return imgs[:_MAX_CANDIDATES]
    except HttpError as e:
        status = getattr(getattr(e, "resp", None), "status", None)
        if status in (403, 404):
            raise DriveAccessError(str(e))
        raise


def download_bytes(drive, file_id):
    """Full file bytes. For media downloads, get_media().execute() returns the
    raw content directly."""
    return drive.files().get_media(fileId=file_id).execute()


def downscale_jpeg(image_bytes, max_px=768, quality=80):
    """Downscale to a max dimension and re-encode JPEG for the vision pass."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
    except (UnidentifiedImageError, OSError) as e:
        raise UnreadableImage(str(e))
    img.thumbnail((max_px, max_px))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality)
    return out.getvalue()


_RUBRIC = (
    "Masi is a two-birds programme: women's employment and children's education. "
    "A story's subject may be a woman, a child, or a woman together with her children. "
    "Using the story context, pick the single strongest image that features THIS story's "
    "subject for a donor email header: subject in sharp focus, warm, uncluttered background, "
    "landscape framing. A woman with her children is on-message, not a group shot to reject. "
    "Reject blurry, duplicate, cut-out-on-transparent, or incoherent crowd shots. "
    "Return ONLY JSON: {\"chosen_index\": int, \"reason\": str, "
    "\"rejected\": [{\"index\": int, \"why\": str}]}."
)


def _text_from_response(response):
    parts = []
    for block in getattr(response, "content", []):
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _extract_json(raw):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        s, e = raw.find("{"), raw.rfind("}")
        if s == -1 or e <= s:
            return None
        try:
            return json.loads(raw[s:e + 1])
        except json.JSONDecodeError:
            return None


def _fallback(reason):
    return {"chosen_index": 0, "reason": reason, "rejected": [], "fallback": True}


def pick_hero(anthropic_client, candidates, story_context):
    """One vision call to choose the hero. Single candidate or any parse
    failure -> fallback to index 0 (never raises)."""
    if len(candidates) == 1:
        return _fallback("only image available")

    content = [{"type": "text", "text": "Story context: " + json.dumps(story_context, default=str)}]
    for i, c in enumerate(candidates):
        content.append({"type": "text", "text": f"Candidate {i}: {c['name']}"})
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": c["b64"]},
        })
    content.append({"type": "text", "text": _RUBRIC})

    response = anthropic_client.messages.create(
        model=MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": content}],
    )
    payload = _extract_json(_text_from_response(response))
    if not isinstance(payload, dict):
        return _fallback("model returned no parseable choice")
    idx = payload.get("chosen_index")
    if not isinstance(idx, int) or not (0 <= idx < len(candidates)):
        return _fallback("model returned an out-of-range choice")
    return {
        "chosen_index": idx,
        "reason": str(payload.get("reason", "")),
        "rejected": payload.get("rejected") or [],
        "fallback": False,
    }
