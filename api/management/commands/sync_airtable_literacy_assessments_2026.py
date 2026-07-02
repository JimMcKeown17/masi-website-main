import os
import re
import time
import requests
from collections import Counter
from datetime import datetime, timezone as dt_timezone
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from dotenv import load_dotenv
from api.models import LiteracyAssessment2026, CanonicalChild, AirtableSyncLog
from api.literacy_2026_grades import grade_is_fallback

SKILL_FIELDS = {
    "Letter Sounds": "letter_sounds", "Story Comprehension": "story_comprehension",
    "Listen First Sound": "listen_first_sound", "Listen Words": "listen_words",
    "Writing Letters": "writing_letters", "Read Words": "read_words",
    "Read Sentences": "read_sentences", "Read Story": "read_story",
    "Write CVCs": "write_cvcs", "Write Sentences": "write_sentences",
    "Write Story": "write_story",
}
UPDATE_FIELDS = [
    "source_created_time", "source_modified_time", "assessment_uid", "child_uid",
    "child_id", "year", "term", "grade", "language", *SKILL_FIELDS.values(), "total",
    "programme_belonging", "duplicate_status", "capture_status", "is_active", "last_seen_at",
]
RETIRE_FLOOR = 25
RETIRE_FRACTION = 0.10
_EMOJI = re.compile(r"[^\w\s\-/]", flags=re.UNICODE)


def _uid(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value or None


def _num(value):
    if isinstance(value, dict):  # Airtable {'specialValue': 'NaN'}
        return None
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_status(value):
    """Strip the leading emoji/symbols Airtable single-selects carry (e.g. '✅ Unique')."""
    value = _uid(value)
    if value is None:
        return None
    cleaned = _EMOJI.sub("", str(value)).strip()
    return cleaned or None


def _dt(value):
    """Parse an Airtable ISO-8601 timestamp into an aware UTC datetime."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt_timezone.utc)
    except (TypeError, ValueError):
        return None


class Command(BaseCommand):
    help = "Sync 2026 literacy assessments from Airtable into LiteracyAssessment2026"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Full extract + QA report, no writes")
        parser.add_argument("--verbose", action="store_true", help="Show sample records")
        parser.add_argument("--allow-retire", action="store_true",
                            help="Retire stale rows even if the retire-delta guard trips (use after verifying a full pull)")

    def handle(self, *args, **options):
        load_dotenv()
        base_id = os.getenv("AIRTABLE_LITERACY_ASSESSMENTS_2026_BASE_ID")
        table_id = os.getenv("AIRTABLE_LITERACY_ASSESSMENTS_2026_TABLE_ID")
        token = os.getenv("AIRTABLE_TOKEN")
        if not all([base_id, table_id, token]):
            self.stdout.write(self.style.ERROR("Missing AIRTABLE_LITERACY_ASSESSMENTS_2026_* / AIRTABLE_TOKEN"))
            return
        is_dry = options["dry_run"]
        if is_dry:
            self.stdout.write(self.style.WARNING("=== DRY RUN — no changes saved ===\n"))
        sync_log = None if is_dry else AirtableSyncLog.objects.create(sync_type="literacy_assessments_2026")
        try:
            records = self.fetch_from_airtable(base_id, table_id, token)
            self.stdout.write(self.style.SUCCESS(f"Fetched {len(records)} records"))
            child_map = {row["child_uid"]: row["id"]
                         for row in CanonicalChild.objects.values("id", "child_uid")}
            report = self.qa_report(records, child_map)
            self._print_report(report)
            if options["verbose"]:
                for r in records[:3]:
                    f = r["fields"]
                    self.stdout.write(f"  {f.get('Assessment UID')} | {_uid(f.get('Child UID'))} | {f.get('Term')} {f.get('Year')}")
            if is_dry:
                self.stdout.write("DRY RUN: no writes.")
                return
            stats = self.bulk_upsert(records, child_map, allow_retire=options["allow_retire"])
            if stats["retire_skipped"]:
                self.stdout.write(self.style.WARNING(
                    f"RETIRE GUARD: skipped retiring {stats['retire_skipped']} rows — the pull looked short. "
                    f"Verify it was complete, then re-run with --allow-retire."))
            if sync_log:
                sync_log.records_processed = len(records)
                sync_log.records_created = stats["created"]
                sync_log.records_updated = stats["updated"]
                sync_log.records_skipped = stats["skipped"]
                sync_log.details = {**report, **stats}
                sync_log.mark_complete(success=True)
            self.stdout.write(self.style.SUCCESS(
                f"Done — created {stats['created']}, updated {stats['updated']}, "
                f"skipped {stats['skipped']}, retired {stats['retired']}, "
                f"retire_skipped {stats['retire_skipped']}, orphans {stats['orphans']}"))
        except Exception as e:
            if sync_log:
                try:
                    sync_log.mark_complete(success=False, error_message=str(e))
                except Exception:
                    pass
            self.stdout.write(self.style.ERROR(f"Sync failed: {e}"))
            raise

    def _print_report(self, report):
        self.stdout.write(
            f"QA: total={report['total']} skipped={report['skipped']} "
            f"null_child_fk={report['null_child_fk']} duplicate_pairs={report['duplicate_pairs']} "
            f"grade_fallbacks={report['grade_fallbacks']} would_retire={report['would_retire']}")

    def extract_row(self, record):
        f = record.get("fields", {})
        child_uid = _uid(f.get("Child UID"))
        term = f.get("Term")
        year = f.get("Year")
        if not child_uid or not term or year is None:
            return None
        row = dict(
            source_created_time=_dt(record.get("createdTime")),
            source_modified_time=_dt(f.get("Last Modified Time") or f.get("Last Modified")),
            assessment_uid=f.get("Assessment UID"),
            child_uid=child_uid,
            year=int(year),
            term=term,
            grade=f.get("Grade"),
            language=f.get("Language"),
            total=_num(f.get("Total")),
            programme_belonging=f.get("Programme Belonging") if isinstance(f.get("Programme Belonging"), list) else [],
            duplicate_status=_clean_status(f.get("Duplicate?") or f.get("Duplicate Status")),
            capture_status=_clean_status(f.get("Capture Status")),
        )
        for at_name, model_field in SKILL_FIELDS.items():
            row[model_field] = _num(f.get(at_name))
        return row

    def qa_report(self, all_records, child_map=None):
        """Full-extraction preflight: what WOULD happen, without writing."""
        child_map = child_map or {}
        total = len(all_records)
        skipped = null_child_fk = grade_fallbacks = 0
        seen_ids, pairs = set(), Counter()
        for rec in all_records:
            rid = rec.get("id")
            data = self.extract_row(rec)
            if not rid or data is None:
                skipped += 1
                continue
            seen_ids.add(rid)
            if data["child_uid"] not in child_map:
                null_child_fk += 1
            if grade_is_fallback(data.get("grade")):
                grade_fallbacks += 1
            # The Assessments DB holds multiple years, so duplicate pairs are
            # per-(child, term, year) — same child/term in different years is legit.
            pairs[(data["child_uid"], data["term"], data["year"])] += 1
        duplicate_pairs = sum(1 for _k, n in pairs.items() if n > 1)
        existing_active = set(LiteracyAssessment2026.objects.filter(is_active=True)
                              .values_list("source_airtable_id", flat=True))
        would_retire = len(existing_active - seen_ids)
        return dict(total=total, skipped=skipped, null_child_fk=null_child_fk,
                    duplicate_pairs=duplicate_pairs, grade_fallbacks=grade_fallbacks,
                    would_retire=would_retire)

    def bulk_upsert(self, all_records, child_map=None, allow_retire=False,
                    retire_floor=RETIRE_FLOOR, retire_fraction=RETIRE_FRACTION):
        child_map = child_map or {}
        now = timezone.now()
        rows = list(LiteracyAssessment2026.objects.values("id", "source_airtable_id", "is_active"))
        existing = {r["source_airtable_id"]: r["id"] for r in rows}       # all rows (update/reactivate)
        active_by_src = {r["source_airtable_id"]: r["id"] for r in rows if r["is_active"]}
        active_count = len(active_by_src)
        new_objs, update_objs, skipped, orphans, seen = [], [], 0, 0, set()
        for record in all_records:
            airtable_id = record.get("id")
            data = self.extract_row(record)
            if not airtable_id or data is None:
                skipped += 1
                continue
            seen.add(airtable_id)
            data["child_id"] = child_map.get(data["child_uid"])
            if data["child_id"] is None:
                orphans += 1
            data["is_active"] = True
            data["last_seen_at"] = now
            if airtable_id in existing:
                update_objs.append(LiteracyAssessment2026(id=existing[airtable_id], source_airtable_id=airtable_id, **data))
            else:
                new_objs.append(LiteracyAssessment2026(source_airtable_id=airtable_id, **data))
        # Only currently-active rows can be retired; already-inactive history is excluded so
        # accumulated dead rows never inflate would_retire or permanently trip the guard.
        stale_ids = [rid for src, rid in active_by_src.items() if src not in seen]
        would_retire = len(stale_ids)
        guard = would_retire > max(retire_floor, int(retire_fraction * active_count))
        retire = bool(stale_ids) and (allow_retire or not guard)
        with transaction.atomic():
            if new_objs:
                LiteracyAssessment2026.objects.bulk_create(new_objs, batch_size=500)
            if update_objs:
                LiteracyAssessment2026.objects.bulk_update(update_objs, UPDATE_FIELDS, batch_size=500)
            retired = 0
            if retire:
                retired = (LiteracyAssessment2026.objects
                           .filter(id__in=stale_ids, is_active=True)
                           .update(is_active=False))
        return {"created": len(new_objs), "updated": len(update_objs), "skipped": skipped,
                "retired": retired, "retire_skipped": would_retire if not retire else 0,
                "orphans": orphans}

    def fetch_from_airtable(self, base_id, table_id, token):
        url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
        headers = {"Authorization": f"Bearer {token}"}
        records = []
        while url:
            resp = requests.get(url, headers=headers)
            if resp.status_code != 200:
                raise ValueError(f"Airtable API error {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            records.extend(data.get("records", []))
            offset = data.get("offset")
            url = f"https://api.airtable.com/v0/{base_id}/{table_id}?offset={offset}" if offset else None
            if offset:
                time.sleep(0.2)
        return records
