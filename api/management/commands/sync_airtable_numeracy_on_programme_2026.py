import os
import time
from collections import Counter

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from dotenv import load_dotenv

from api.management.commands.sync_airtable_numeracy_assessments_2026 import (
    RETIRE_FLOOR,
    RETIRE_FRACTION,
)
from api.models import AirtableSyncLog, CanonicalChild, NumeracyOnTheProgramme2026
from api.numeracy_2026 import list_value, parse_int, uid_value


UPDATE_FIELDS = [
    "source_airtable_id",
    "child_uid",
    "child_id",
    "programme_status",
    "programme_belonging",
    "grade",
    "school",
    "mentor",
    "numeracy_coach",
    "total_sessions",
    "session_school_count",
    "source_session_ids",
    "is_active",
    "last_seen_at",
]


class Command(BaseCommand):
    help = "Sync the 2026 numeracy programme roster from Airtable"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--verbose", action="store_true")
        parser.add_argument("--allow-retire", action="store_true")

    def handle(self, *args, **options):
        load_dotenv()
        base_id = os.getenv("AIRTABLE_NUMERACY_ON_THE_PROGRAMME_2026_BASE_ID")
        table_id = os.getenv("AIRTABLE_NUMERACY_ON_THE_PROGRAMME_2026_TABLE_ID")
        token = os.getenv("AIRTABLE_TOKEN") or os.getenv("AIRTABLE_API_KEY")
        if not all((base_id, table_id, token)):
            raise CommandError("Missing numeracy roster Airtable configuration")
        dry_run = options["dry_run"]
        log = None if dry_run else AirtableSyncLog.objects.create(
            sync_type="numeracy_on_the_programme_2026"
        )
        try:
            records = self.fetch_from_airtable(base_id.strip(), table_id.strip(), token.strip())
            child_map = dict(CanonicalChild.objects.values_list("child_uid", "id"))
            report = self.qa_report(records, child_map)
            self.stdout.write(f"QA {report}")
            if log:
                log.details = report
                log.save(update_fields=["details"])
            if report["duplicate_child_uids"]:
                raise ValueError(
                    f"duplicate child_uid values in roster pull: {report['duplicate_child_uids']}"
                )
            if dry_run:
                self.stdout.write("DRY RUN: no database writes")
                return
            stats = self.bulk_upsert(records, child_map, allow_retire=options["allow_retire"])
            log.records_processed = len(records)
            log.records_created = stats["created"]
            log.records_updated = stats["updated"]
            log.records_skipped = stats["skipped"]
            log.details = {**report, **stats}
            log.mark_complete(success=True)
            self.stdout.write(self.style.SUCCESS(f"Roster sync complete: {stats}"))
        except Exception as exc:
            if log:
                log.mark_complete(success=False, error_message=str(exc))
            raise

    def extract_row(self, record):
        fields = record.get("fields", {})
        child_uid = uid_value(fields.get("Child UID"))
        if not child_uid:
            return None
        return {
            "child_uid": child_uid,
            "programme_status": uid_value(fields.get("2026 On The Programme")),
            "programme_belonging": list_value(fields.get("Programme Belonging")),
            "grade": uid_value(fields.get("Grade")),
            "school": uid_value(fields.get("School (from Sessions)")),
            "mentor": uid_value(fields.get("Mentor (from Sessions)")),
            "numeracy_coach": uid_value(fields.get("Numeracy Coach Name (from Sessions)")),
            "total_sessions": parse_int(fields.get("Total Sessions")),
            "session_school_count": parse_int(fields.get("Session School Count")),
            "source_session_ids": [
                str(value) for value in list_value(fields.get("Sessions")) if str(value).startswith("rec")
            ],
        }

    def qa_report(self, records, child_map=None):
        child_map = child_map or {}
        rows = [self.extract_row(record) for record in records]
        valid = [row for row in rows if row is not None]
        counts = Counter(row["child_uid"] for row in valid)
        duplicate_uids = sorted(uid for uid, count in counts.items() if count > 1)
        seen_sources = {
            record.get("id")
            for record, row in zip(records, rows)
            if record.get("id") and row is not None
        }
        active_sources = set(
            NumeracyOnTheProgramme2026.objects.filter(is_active=True).values_list(
                "source_airtable_id", flat=True
            )
        )
        return {
            "total": len(records),
            "valid": len(valid),
            "blank_child_uids": len(rows) - len(valid),
            "duplicate_child_uids": duplicate_uids,
            "canonical_orphans": sum(row["child_uid"] not in child_map for row in valid),
            "would_retire": len(active_sources - seen_sources),
        }

    def bulk_upsert(
        self,
        records,
        child_map=None,
        allow_retire=False,
        retire_floor=RETIRE_FLOOR,
        retire_fraction=RETIRE_FRACTION,
    ):
        child_map = child_map or {}
        parsed = []
        skipped = 0
        for record in sorted(records, key=lambda item: str(item.get("id") or "")):
            source_id = record.get("id")
            row = self.extract_row(record)
            if not source_id or row is None:
                skipped += 1
                continue
            parsed.append((source_id, row))
        counts = Counter(row["child_uid"] for _source_id, row in parsed)
        duplicates = sorted(uid for uid, count in counts.items() if count > 1)
        if duplicates:
            raise ValueError(f"duplicate child_uid values in roster pull: {duplicates}")

        existing_rows = list(
            NumeracyOnTheProgramme2026.objects.values(
                "id", "source_airtable_id", "child_uid", "is_active"
            )
        )
        by_source = {row["source_airtable_id"]: row for row in existing_rows}
        by_uid = {row["child_uid"]: row for row in existing_rows}
        active = {
            row["source_airtable_id"]: row["id"] for row in existing_rows if row["is_active"]
        }
        now = timezone.now()
        creates, updates, claimed, seen_sources = [], [], set(), set()
        orphans = 0
        for source_id, data in parsed:
            source_match = by_source.get(source_id)
            uid_match = by_uid.get(data["child_uid"])
            if source_match and uid_match and source_match["id"] != uid_match["id"]:
                raise ValueError(
                    f"source ID {source_id} and child_uid {data['child_uid']} resolve to different rows"
                )
            match = source_match or uid_match
            if match and match["id"] in claimed:
                raise ValueError(f"duplicate child_uid target for {data['child_uid']}")
            data["child_id"] = child_map.get(data["child_uid"])
            if data["child_id"] is None:
                orphans += 1
            data["is_active"] = True
            data["last_seen_at"] = now
            seen_sources.add(source_id)
            if match:
                claimed.add(match["id"])
                updates.append(
                    NumeracyOnTheProgramme2026(
                        id=match["id"], source_airtable_id=source_id, **data
                    )
                )
            else:
                creates.append(
                    NumeracyOnTheProgramme2026(source_airtable_id=source_id, **data)
                )
        stale_ids = [
            row_id
            for source_id, row_id in active.items()
            if source_id not in seen_sources and row_id not in claimed
        ]
        guard = len(stale_ids) > max(retire_floor, int(retire_fraction * len(active)))
        may_retire = bool(stale_ids) and (allow_retire or not guard)
        with transaction.atomic():
            if creates:
                NumeracyOnTheProgramme2026.objects.bulk_create(creates, batch_size=500)
            if updates:
                NumeracyOnTheProgramme2026.objects.bulk_update(updates, UPDATE_FIELDS, batch_size=500)
            retired = 0
            if may_retire:
                retired = NumeracyOnTheProgramme2026.objects.filter(
                    id__in=stale_ids, is_active=True
                ).update(is_active=False)
        return {
            "created": len(creates),
            "updated": len(updates),
            "skipped": skipped,
            "orphans": orphans,
            "retired": retired,
            "retire_skipped": len(stale_ids) if stale_ids and not may_retire else 0,
        }

    def fetch_from_airtable(self, base_id, table_id, token):
        url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"pageSize": 100}
        records = []
        while True:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            if response.status_code != 200:
                raise CommandError(
                    f"Airtable API error {response.status_code}: {response.text[:200]}"
                )
            payload = response.json()
            records.extend(payload.get("records", []))
            offset = payload.get("offset")
            if not offset:
                return records
            params["offset"] = offset
            time.sleep(0.2)
