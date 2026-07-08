import base64

from django.core.management.base import BaseCommand

from fundraising.models import ContentStory
from fundraising.services import photos, photos_report


class Command(BaseCommand):
    help = "Curate one hero photo per Success Story and cache it on GCS (ADR 0008)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Re-pick stories that already have a hero")
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--story", type=str, default=None, help="A single source_airtable_id")
        parser.add_argument("--dry-run", action="store_true", help="Pick and report, but do not upload or save")
        parser.add_argument("--report", type=str, default="fundraising_hero_contact_sheet.html")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        # is_active gate per review (all 87 are active today; future-proof). No consent
        # gate by decision (Jim, 2026-07-08) - see "Review decisions" in the plan.
        qs = ContentStory.objects.filter(is_active=True).exclude(drive_link="").order_by("-date_published")
        if opts["story"]:
            qs = qs.filter(source_airtable_id=opts["story"])
        elif not opts["force"]:
            qs = qs.filter(hero_image_url="")
        if opts["limit"]:
            qs = qs[:opts["limit"]]

        drive = photos.drive_client()
        client = photos.anthropic_client()
        bucket = None if dry else photos.gcs_bucket()

        records, stored, fallback, problems = [], 0, 0, 0
        for story in qs:
            rec = self._process(story, drive, client, bucket, dry)
            records.append(rec)
            if rec["status"] == "problem":
                problems += 1
            else:
                stored += 1
                fallback += 1 if rec["fallback"] else 0

        html = photos_report.render_contact_sheet(records)
        with open(opts["report"], "w", encoding="utf-8") as fh:
            fh.write(html)
        self.stdout.write(self.style.SUCCESS(
            f"stored={stored} (fallback={fallback}) problems={problems}"
            f"{' [dry-run]' if dry else ''} -> {opts['report']}"))

    def _process(self, story, drive, client, bucket, dry):
        base = {"title": str(story), "meta": _meta(story), "fallback": False,
                "chosen_index": None, "reason": "", "hero_url": None,
                "candidates": [], "problem_reason": None}
        try:
            kind, ref_id = photos.parse_drive_ref(story.drive_link)
            if kind is None:
                return {**base, "status": "problem", "problem_reason": "no usable link (search URL or empty)"}
            try:
                candidates = photos.list_candidate_images(drive, kind, ref_id)
            except photos.DriveAccessError:
                return {**base, "status": "problem", "problem_reason": "drive 404 (not shared or deleted)"}
            if not candidates:
                return {**base, "status": "problem", "problem_reason": "no images (video-only or empty folder)"}

            thumbs, full = [], []
            for c in candidates:
                try:
                    raw = photos.download_bytes(drive, c["id"])
                    thumb = photos.downscale_jpeg(raw)
                except photos.UnreadableImage:
                    continue
                thumbs.append({"name": c["name"], "b64": base64.b64encode(thumb).decode()})
                full.append((raw, c.get("mimeType", "image/jpeg")))
            if not thumbs:
                return {**base, "status": "problem", "problem_reason": "no readable images"}

            context = {"feature_name": story.feature_name, "headline": story.headline,
                       "narrative": (story.narrative or "")[:600], "category": story.category}
            pick = photos.pick_hero(client, thumbs, context)
            # Multi-candidate fallback = the model could not choose. Do NOT publish an
            # arbitrary image; surface as a problem for a manual re-run. Only the
            # single-candidate fallback (the sole image) proceeds to store.
            if pick["fallback"] and len(thumbs) > 1:
                return {**base, "status": "problem",
                        "problem_reason": f"model could not pick a hero ({pick['reason']}); needs manual choice"}
            idx = pick["chosen_index"]
            raw, mime = full[idx]

            hero_url = None
            if not dry:
                hero_url = photos.upload_hero(bucket, story, raw, mime)
                story.hero_image_url = hero_url
                story.save(update_fields=["hero_image_url", "updated_at"])

            rej = {r.get("index"): r.get("why") for r in pick.get("rejected", []) if isinstance(r, dict)}
            cands = [{"name": t["name"], "b64": t["b64"],
                      "rejected_why": None if i == idx else rej.get(i)} for i, t in enumerate(thumbs)]
            return {**base, "status": "dry" if dry else "stored", "fallback": pick["fallback"],
                    "chosen_index": idx, "reason": pick["reason"], "hero_url": hero_url, "candidates": cands}
        except Exception as e:  # never abort the batch on one story
            return {**base, "status": "problem", "problem_reason": f"error: {e}"}


def _meta(story):
    parts = []
    if story.school:
        parts.append(", ".join(story.school) if isinstance(story.school, list) else str(story.school))
    if story.date_published:
        parts.append(str(story.date_published))
    return " - ".join(parts)
