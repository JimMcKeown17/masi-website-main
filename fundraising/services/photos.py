"""Story hero photo curation: Drive read -> vision pick -> GCS cache. See
_plans/fundraising-hero-photos-spec.md and ADR 0008."""
import base64
import io
import json
import os
import re

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
