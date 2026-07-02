import os
import time
import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from dotenv import load_dotenv
from api.models import OnTheProgramme2026, AirtableSyncLog
from api.management.commands.sync_airtable_literacy_assessments_2026 import (
    _uid, _num, RETIRE_FLOOR, RETIRE_FRACTION,
)

UPDATE_FIELDS = ["source_airtable_id", "child_uid", "on_the_programme", "mentor", "school",
                 "grade", "all_sessions_count", "valid_learning_records_count",
                 "is_active", "last_seen_at"]


def _int(value):
    n = _num(value)
    return int(n) if n is not None else None


class Command(BaseCommand):
    help = "Sync the 2026 On The Programme roster into OnTheProgramme2026"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--verbose", action="store_true")
        parser.add_argument("--allow-retire", action="store_true")

    def handle(self, *args, **options):
        load_dotenv()
        base_id = os.getenv("AIRTABLE_ON_THE_PROGRAMME_2026_BASE_ID")
        table_id = os.getenv("AIRTABLE_ON_THE_PROGRAMME_2026_TABLE_ID")
        token = os.getenv("AIRTABLE_TOKEN")
        if not all([base_id, table_id, token]):
            self.stdout.write(self.style.ERROR("Missing AIRTABLE_ON_THE_PROGRAMME_2026_* / AIRTABLE_TOKEN"))
            return
        is_dry = options["dry_run"]
        if is_dry:
            self.stdout.write(self.style.WARNING("=== DRY RUN ===\n"))
        sync_log = None if is_dry else AirtableSyncLog.objects.create(sync_type="on_the_programme_2026")
        try:
            records = self.fetch_from_airtable(base_id, table_id, token)
            self.stdout.write(self.style.SUCCESS(f"Fetched {len(records)} roster records"))
            existing_active = set(OnTheProgramme2026.objects.filter(is_active=True)
                                  .values_list("source_airtable_id", flat=True))
            seen = {r.get("id") for r in records if self.extract_row(r) is not None}
            self.stdout.write(f"QA: total={len(records)} would_retire={len(existing_active - seen)}")
            if is_dry:
                self.stdout.write("DRY RUN: no writes.")
                return
            stats = self.bulk_upsert(records, allow_retire=options["allow_retire"])
            if stats["retire_skipped"]:
                self.stdout.write(self.style.WARNING(
                    f"RETIRE GUARD: skipped retiring {stats['retire_skipped']} rows — pull looked short. "
                    f"Verify, then re-run with --allow-retire."))
            if stats["dup_uid_skipped"]:
                self.stdout.write(self.style.WARNING(
                    f"DUP GUARD: skipped {stats['dup_uid_skipped']} duplicate roster child_uid rows — "
                    f"resolve them in Airtable (the export refuses while this is > 0)."))
            if sync_log:
                sync_log.records_processed = len(records)
                sync_log.records_created = stats["created"]
                sync_log.records_updated = stats["updated"]
                sync_log.records_skipped = stats["skipped"]
                sync_log.details = stats
                sync_log.mark_complete(success=True)
            self.stdout.write(self.style.SUCCESS(
                f"Done — created {stats['created']}, updated {stats['updated']}, "
                f"skipped {stats['skipped']}, retired {stats['retired']}, retire_skipped {stats['retire_skipped']}"))
        except Exception as e:
            if sync_log:
                try:
                    sync_log.mark_complete(success=False, error_message=str(e))
                except Exception:
                    pass
            self.stdout.write(self.style.ERROR(f"Sync failed: {e}"))
            raise

    def extract_row(self, record):
        f = record.get("fields", {})
        child_uid = _uid(f.get("Child UID"))
        if not child_uid:
            return None
        return dict(
            child_uid=child_uid,
            on_the_programme=(f.get("2026 On The Programme") == "Yes"),
            mentor=_uid(f.get("Mentor")),
            school=f.get("School"),
            grade=_uid(f.get("Actual Grade")) or f.get("Resolved Grade 2026"),
            all_sessions_count=_int(f.get("All Sessions Count v2")),
            valid_learning_records_count=_int(f.get("Valid Learning Records Count v2")),
        )

    def bulk_upsert(self, all_records, allow_retire=False,
                    retire_floor=RETIRE_FLOOR, retire_fraction=RETIRE_FRACTION):
        now = timezone.now()
        rows = list(OnTheProgramme2026.objects.values("id", "source_airtable_id", "child_uid", "is_active"))
        existing_by_src = {r["source_airtable_id"]: r["id"] for r in rows}
        existing_by_uid = {r["child_uid"]: r["id"] for r in rows}
        active_by_src = {r["source_airtable_id"]: r["id"] for r in rows if r["is_active"]}
        active_count = len(active_by_src)
        # Deterministic regardless of Airtable page ordering (R3-5).
        ordered = sorted(all_records, key=lambda r: str(r.get("id") or ""))
        new_objs, update_objs, skipped, dup_uid_skipped = [], [], 0, 0
        seen_src, seen_uid, claimed = set(), set(), set()
        for record in ordered:
            airtable_id = record.get("id")
            data = self.extract_row(record)
            if not airtable_id or data is None:
                skipped += 1
                continue
            uid = data["child_uid"]
            if uid in seen_uid:          # within-batch duplicate child_uid (roster anomaly) — fail-closed via export gate
                skipped += 1
                dup_uid_skipped += 1
                continue
            # Resolve to an existing row by record id FIRST, then by child_uid (adopt the new id).
            row_id = existing_by_src.get(airtable_id) or existing_by_uid.get(uid)
            if row_id is not None and row_id in claimed:  # two incoming records target one row (R3-5)
                skipped += 1
                dup_uid_skipped += 1
                continue
            seen_uid.add(uid)
            seen_src.add(airtable_id)
            data["is_active"] = True
            data["last_seen_at"] = now
            if row_id is not None:
                claimed.add(row_id)
                update_objs.append(OnTheProgramme2026(id=row_id, source_airtable_id=airtable_id, **data))
            else:
                new_objs.append(OnTheProgramme2026(source_airtable_id=airtable_id, **data))
        # Retire ACTIVE rows whose record id vanished AND that we didn't adopt onto this run.
        stale_ids = [rid for aid, rid in active_by_src.items()
                     if aid not in seen_src and rid not in claimed]
        would_retire = len(stale_ids)
        guard = would_retire > max(retire_floor, int(retire_fraction * active_count))
        retire = bool(stale_ids) and (allow_retire or not guard)
        with transaction.atomic():
            if new_objs:
                OnTheProgramme2026.objects.bulk_create(new_objs, batch_size=500)
            if update_objs:
                OnTheProgramme2026.objects.bulk_update(update_objs, UPDATE_FIELDS, batch_size=500)
            retired = 0
            if retire:
                retired = (OnTheProgramme2026.objects
                           .filter(id__in=stale_ids, is_active=True)
                           .update(is_active=False))
        return {"created": len(new_objs), "updated": len(update_objs), "skipped": skipped,
                "dup_uid_skipped": dup_uid_skipped,
                "retired": retired, "retire_skipped": would_retire if not retire else 0}

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
