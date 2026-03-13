import os
import requests
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.db import transaction
from dotenv import load_dotenv
from api.models import NumeracySession2026, AirtableSyncLog, Youth, School


class Command(BaseCommand):
    """
    Syncs 2026 numeracy session data from Airtable into NumeracySession2026.

    Key differences from 2025 numeracy:
    - Uses UIDs (YTH-XXXX, SCH-XXXXX, CH-XXXXX) for cross-table references
    - Sessions have 3-10 children (a group), not one child per row
    - Data is group-level: Group Current Count Level, Group Current Number Recognition
    - Grain: one Airtable record = one Postgres row

    Upsert key: source_airtable_id (unique Airtable record ID).
    Uses bulk operations for performance.

    Required env vars:
      AIRTABLE_NUMERACY_2026_BASE_ID   = appiWLloU1EVXDIxM
      AIRTABLE_NUMERACY_2026_TABLE_ID  = tblw7FP4NT0oM6U9p
      AIRTABLE_TOKEN
    """
    help = "Sync 2026 numeracy session data from Airtable"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Preview without saving')
        parser.add_argument('--verbose', action='store_true', help='Show sample records fetched')

    def handle(self, *args, **options):
        load_dotenv()
        base_id = os.getenv("AIRTABLE_NUMERACY_2026_BASE_ID")
        table_id = os.getenv("AIRTABLE_NUMERACY_2026_TABLE_ID")
        token = os.getenv("AIRTABLE_TOKEN")
        is_dry_run = options['dry_run']

        if not all([base_id, table_id, token]):
            self.stdout.write(self.style.ERROR(
                "Missing env vars. Required:\n"
                f"  AIRTABLE_NUMERACY_2026_BASE_ID: {bool(base_id)}\n"
                f"  AIRTABLE_NUMERACY_2026_TABLE_ID: {bool(table_id)}\n"
                f"  AIRTABLE_TOKEN: {bool(token)}"
            ))
            return

        if is_dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN MODE — no changes will be saved ===\n"))

        # Build FK lookup dicts for resolving UIDs to canonical records
        self.youth_by_uid = {y.youth_uid: y for y in Youth.objects.filter(youth_uid__isnull=False)}
        self.school_by_uid = {s.school_uid: s for s in School.objects.filter(school_uid__isnull=False)}
        self.stdout.write(f"FK lookups: youth={len(self.youth_by_uid)}, school={len(self.school_by_uid)}")

        sync_log = None
        if not is_dry_run:
            sync_log = AirtableSyncLog.objects.create(sync_type='numeracy_sessions_2026')
            self.stdout.write(f"Sync log started (ID: {sync_log.id})")

        try:
            all_records = self.fetch_from_airtable(base_id, table_id, token)
            self.stdout.write(self.style.SUCCESS(f"Fetched {len(all_records)} records from Airtable"))

            if options['verbose']:
                for r in all_records[:3]:
                    f = r['fields']
                    self.stdout.write(
                        f"  Sample: {f.get('Session UID')} | "
                        f"{f.get('Session Date')} | "
                        f"youth={f.get('Youth UID')} | "
                        f"school={f.get('School UID')} | "
                        f"children={f.get('Child UID')} | "
                        f"count_level={f.get('Group Current Count Level')}"
                    )

            db_count = NumeracySession2026.objects.count()

            if is_dry_run:
                self.stdout.write(f"DRY RUN: would process {len(all_records)} records")
                self.stdout.write(f"Current row count in DB: {db_count}")
                return

            stats = self.bulk_upsert(all_records)

            if sync_log:
                sync_log.records_processed = len(all_records)
                sync_log.records_created = stats['created']
                sync_log.records_updated = stats['updated']
                sync_log.records_skipped = stats['skipped']
                sync_log.mark_complete(success=True)

            self.stdout.write(self.style.SUCCESS(
                f"\nSync complete — "
                f"Airtable records: {len(all_records)}, "
                f"created: {stats['created']}, "
                f"updated: {stats['updated']}, "
                f"skipped: {stats['skipped']}"
            ))

        except Exception as e:
            if sync_log:
                try:
                    sync_log.mark_complete(success=False, error_message=str(e))
                except Exception:
                    pass
            self.stdout.write(self.style.ERROR(f"Sync failed: {e}"))
            raise

    def bulk_upsert(self, all_records):
        existing = {
            row['source_airtable_id']: row['id']
            for row in NumeracySession2026.objects.values('id', 'source_airtable_id')
        }

        new_objs = []
        update_objs = []
        skipped = 0

        for record in all_records:
            airtable_id = record.get('id')
            if not airtable_id:
                skipped += 1
                continue

            row_data = self.extract_row(record)

            if airtable_id in existing:
                obj = NumeracySession2026(id=existing[airtable_id], source_airtable_id=airtable_id, **row_data)
                update_objs.append(obj)
            else:
                new_objs.append(NumeracySession2026(source_airtable_id=airtable_id, **row_data))

        update_fields = [
            'session_record', 'session_uid', 'session_date',
            'youth_uid', 'school_uid', 'child_uids', 'children_count',
            'youth_id', 'school_id',
            'group_count_level', 'group_number_recognition',
            'duplicate_status', 'overall_session_status',
            'capture_delay', 'capture_delay_flag', 'duplicate_fingerprint',
            'created_in_airtable',
        ]

        with transaction.atomic():
            if new_objs:
                NumeracySession2026.objects.bulk_create(new_objs, batch_size=500)
            if update_objs:
                NumeracySession2026.objects.bulk_update(update_objs, update_fields, batch_size=500)

        return {'created': len(new_objs), 'updated': len(update_objs), 'skipped': skipped}

    def extract_row(self, record):
        fields = record.get('fields', {})

        def safe_first(name):
            val = fields.get(name)
            if isinstance(val, list):
                return val[0] if val else None
            return val or None

        def strip_emoji(val):
            """Strip leading emoji from values like '🟢 31-40' → '31-40'."""
            if not val:
                return val
            return val.encode('ascii', 'ignore').decode().strip(' -')

        youth_uid_val = safe_first('Youth UID')
        school_uid_val = safe_first('School UID')

        return dict(
            session_record=fields.get('Session Record'),
            session_uid=fields.get('Session UID'),
            session_date=parse_date(fields.get('Session Date', '') or ''),
            youth_uid=youth_uid_val,
            school_uid=school_uid_val,
            youth=self.youth_by_uid.get(youth_uid_val),
            school=self.school_by_uid.get(school_uid_val),
            child_uids=fields.get('Child UID', []),
            children_count=fields.get('Children Count'),
            group_count_level=strip_emoji(fields.get('Group Current Count Level')),
            group_number_recognition=fields.get('Group Current Number Recognition'),
            duplicate_status=strip_emoji(safe_first('Duplicate?')),
            overall_session_status=strip_emoji(fields.get('Overall Session Status')),
            capture_delay=fields.get('Capture Delay'),
            capture_delay_flag=strip_emoji(fields.get('Capture Delay Flag')),
            duplicate_fingerprint=fields.get('Duplicate Fingerprint'),
            created_in_airtable=parse_date(fields.get('Created', '') or ''),
        )

    def fetch_from_airtable(self, base_id, table_id, token):
        url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
        headers = {"Authorization": f"Bearer {token}"}
        all_records = []

        while url:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                raise ValueError(f"Airtable API error {response.status_code}: {response.text[:200]}")
            data = response.json()
            all_records.extend(data.get('records', []))
            offset = data.get('offset')
            url = f"https://api.airtable.com/v0/{base_id}/{table_id}?offset={offset}" if offset else None

        return all_records
