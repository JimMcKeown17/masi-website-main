import os
import time
from collections import Counter, defaultdict

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from dotenv import load_dotenv

from api.models import AirtableSyncLog, CanonicalChild, NumeracyAssessment2026
from api.numeracy_2026 import (
    COMPONENTS,
    evaluate_quality,
    linked_record_ids,
    list_value,
    parse_datetime,
    parse_numeric,
    score_tuple,
    uid_value,
)


RETIRE_FLOOR = 25
RETIRE_FRACTION = 0.10
UPDATE_FIELDS = [
    "source_created_time",
    "assessment_uid",
    "child_uid",
    "child_id",
    "year",
    "term",
    "grade",
    *(component.model_field for component in COMPONENTS),
    "total_raw",
    "assessment_percent",
    "programme_belonging",
    "source_child_ids",
    "source_school_ids",
    "source_assessor_ids",
    "is_active",
    "last_seen_at",
]


class Command(BaseCommand):
    help = "Sync raw numeracy assessment events from Airtable"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--verbose", action="store_true")
        parser.add_argument("--allow-retire", action="store_true")

    def handle(self, *args, **options):
        load_dotenv()
        base_id = os.getenv("AIRTABLE_NUMERACY_2026_ASSESSMENTS_BASE_ID")
        table_id = os.getenv("AIRTABLE_NUMERACY_2026_ASSESSMENTS_TABLE_ID")
        token = os.getenv("AIRTABLE_TOKEN") or os.getenv("AIRTABLE_API_KEY")
        if not all((base_id, table_id, token)):
            raise CommandError("Missing numeracy assessment Airtable configuration")

        dry_run = options["dry_run"]
        log = None if dry_run else AirtableSyncLog.objects.create(sync_type="numeracy_assessments_2026")
        try:
            records = self.fetch_from_airtable(base_id.strip(), table_id.strip(), token.strip())
            child_map = dict(CanonicalChild.objects.values_list("child_uid", "id"))
            report = self.qa_report(records, child_map)
            self._print_report(report)
            if options["verbose"]:
                for item in records[:3]:
                    fields = item.get("fields", {})
                    self.stdout.write(
                        f"{item.get('id')} | {uid_value(fields.get('Child UID'))} | "
                        f"{fields.get('Year')} {fields.get('Term')}"
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
            self.stdout.write(
                self.style.SUCCESS(
                    f"created={stats['created']} updated={stats['updated']} "
                    f"retired={stats['retired']} retire_skipped={stats['retire_skipped']}"
                )
            )
        except Exception as exc:
            if log:
                log.mark_complete(success=False, error_message=str(exc))
            raise

    def extract_row(self, record):
        fields = record.get("fields", {})
        year = parse_numeric(fields.get("Year"))
        term = uid_value(fields.get("Term"))
        if year is None or not term:
            return None
        row = {
            "source_created_time": parse_datetime(record.get("createdTime")),
            "assessment_uid": uid_value(fields.get("Assessment UID")),
            "child_uid": uid_value(fields.get("Child UID")),
            "year": int(year),
            "term": term,
            "grade": uid_value(fields.get("Grade")),
            "total_raw": parse_numeric(fields.get("Total (162)")),
            "assessment_percent": parse_numeric(fields.get("Assessment %")),
            "programme_belonging": list_value(fields.get("Programme Belonging")),
            "source_child_ids": sorted(
                set(linked_record_ids(fields.get("Child DB")) + linked_record_ids(fields.get("Child DB 2")))
            ),
            "source_school_ids": linked_record_ids(fields.get("School Name")),
            "source_assessor_ids": linked_record_ids(fields.get("Assessor")),
        }
        for component in COMPONENTS:
            row[component.model_field] = parse_numeric(fields.get(component.airtable_field))
        return row

    def qa_report(self, records, child_map=None):
        child_map = child_map or {}
        parsed = []
        skipped = 0
        term_year = Counter()
        for record in records:
            row = self.extract_row(record)
            if not record.get("id") or row is None:
                skipped += 1
                continue
            parsed.append({"source_airtable_id": record["id"], **row})
            term_year[f"{row['year']}:{row['term']}"] += 1

        groups = defaultdict(list)
        for row in parsed:
            if row.get("child_uid"):
                groups[(row["child_uid"], row["year"], row["term"])].append(row)
        duplicate_groups = sum(len(group) > 1 for group in groups.values())
        conflicting_groups = sum(
            len(group) > 1 and len({score_tuple(row) for row in group}) > 1
            for group in groups.values()
        )
        _winners, issues = evaluate_quality(parsed)
        range_counts = Counter(
            issue["component"] for issue in issues if issue["issue_code"] == "OUT_OF_RANGE"
        )
        missing = sum(row.get("child_uid") is None for row in parsed)
        h1_rows = [
            row for row in parsed if row["year"] == 2026 and row["term"] in ("Jan", "Jun")
        ]
        missing_h1 = sum(row.get("child_uid") is None for row in h1_rows)
        orphan_h1_uids = sorted(
            {
                row["child_uid"]
                for row in h1_rows
                if row.get("child_uid") and row["child_uid"] not in child_map
            }
        )
        orphans = sum(
            bool(row.get("child_uid")) and row["child_uid"] not in child_map for row in parsed
        )
        seen = {row["source_airtable_id"] for row in parsed}
        active = set(
            NumeracyAssessment2026.objects.filter(is_active=True).values_list(
                "source_airtable_id", flat=True
            )
        )
        return {
            "total": len(records),
            "parsed": len(parsed),
            "skipped_invalid_shape": skipped,
            "term_year_counts": dict(sorted(term_year.items())),
            "missing_child_uids": missing,
            "missing_h1_child_uids": missing_h1,
            "canonical_orphans": orphans,
            "canonical_orphan_h1_uids": orphan_h1_uids,
            "duplicate_groups": duplicate_groups,
            "conflicting_duplicate_groups": conflicting_groups,
            "out_of_range_by_component": dict(sorted(range_counts.items())),
            "would_retire": len(active - seen),
        }

    def _print_report(self, report):
        self.stdout.write(
            "QA " + " ".join(
                f"{key}={report[key]}"
                for key in (
                    "total",
                    "parsed",
                    "missing_child_uids",
                    "missing_h1_child_uids",
                    "canonical_orphans",
                    "duplicate_groups",
                    "conflicting_duplicate_groups",
                    "would_retire",
                )
            )
        )
        self.stdout.write(f"QA term_year_counts={report['term_year_counts']}")
        self.stdout.write(f"QA out_of_range_by_component={report['out_of_range_by_component']}")

    def bulk_upsert(
        self,
        records,
        child_map=None,
        allow_retire=False,
        retire_floor=RETIRE_FLOOR,
        retire_fraction=RETIRE_FRACTION,
    ):
        child_map = child_map or {}
        now = timezone.now()
        existing_rows = list(
            NumeracyAssessment2026.objects.values("id", "source_airtable_id", "is_active")
        )
        existing = {row["source_airtable_id"]: row["id"] for row in existing_rows}
        active = {
            row["source_airtable_id"]: row["id"] for row in existing_rows if row["is_active"]
        }
        creates, updates, seen = [], [], set()
        skipped = orphans = 0
        for record in sorted(records, key=lambda item: str(item.get("id") or "")):
            source_id = record.get("id")
            data = self.extract_row(record)
            if not source_id or data is None:
                skipped += 1
                continue
            seen.add(source_id)
            data["child_id"] = child_map.get(data.get("child_uid"))
            if data.get("child_uid") and data["child_id"] is None:
                orphans += 1
            data["is_active"] = True
            data["last_seen_at"] = now
            if source_id in existing:
                updates.append(
                    NumeracyAssessment2026(
                        id=existing[source_id], source_airtable_id=source_id, **data
                    )
                )
            else:
                creates.append(NumeracyAssessment2026(source_airtable_id=source_id, **data))

        stale_ids = [row_id for source_id, row_id in active.items() if source_id not in seen]
        guard = len(stale_ids) > max(retire_floor, int(retire_fraction * len(active)))
        may_retire = bool(stale_ids) and (allow_retire or not guard)
        with transaction.atomic():
            if creates:
                NumeracyAssessment2026.objects.bulk_create(creates, batch_size=500)
            if updates:
                NumeracyAssessment2026.objects.bulk_update(updates, UPDATE_FIELDS, batch_size=500)
            retired = 0
            if may_retire:
                retired = NumeracyAssessment2026.objects.filter(
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
