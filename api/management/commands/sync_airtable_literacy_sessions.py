import os
import requests
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.db import transaction
from dotenv import load_dotenv
from api.models import LiteracySession, AirtableSyncLog


class Command(BaseCommand):
    """
    Syncs literacy session data from Airtable into LiteracySession.

    GRAIN: One Airtable record = one Postgres row.
    Upsert key: session_id (the business ID assigned by Airtable, not the record ID).

    IMPORTANT: Postgres may have more rows than Airtable if records were deleted in
    Airtable after being synced. Those orphan rows are preserved (never deleted here).
    Query for them with: SELECT COUNT(*) FROM api_literacysession WHERE session_id NOT IN (...)

    Uses bulk operations for performance — fetches all existing session_ids in one query,
    then bulk_create new rows and bulk_update changed rows.
    """
    help = "Sync literacy session data from Airtable using bulk upsert"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Preview without saving')
        parser.add_argument('--verbose', action='store_true', help='Show created/updated counts per batch')

    def handle(self, *args, **options):
        load_dotenv()
        base_id = os.getenv("AIRTABLE_MASI_WEEKLY_SESSIONS_BASE_ID")
        table_name = os.getenv("AIRTABLE_MASI_WEEKLY_SESSIONS_TABLE_NAME")
        token = os.getenv("AIRTABLE_TOKEN")
        is_dry_run = options['dry_run']

        if not all([base_id, table_name, token]):
            self.stdout.write(self.style.ERROR(
                f"Missing Airtable credentials.\n"
                f"  AIRTABLE_MASI_WEEKLY_SESSIONS_BASE_ID: {bool(base_id)}\n"
                f"  AIRTABLE_MASI_WEEKLY_SESSIONS_TABLE_NAME: {bool(table_name)}\n"
                f"  AIRTABLE_TOKEN: {bool(token)}"
            ))
            return

        if is_dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN MODE — no changes will be saved ===\n"))

        sync_log = None
        if not is_dry_run:
            sync_log = AirtableSyncLog.objects.create(sync_type='literacy_sessions')
            self.stdout.write(f"Sync log started (ID: {sync_log.id})")

        try:
            all_records = self.fetch_from_airtable(base_id, table_name, token)
            self.stdout.write(self.style.SUCCESS(f"Fetched {len(all_records)} records from Airtable"))

            db_count = LiteracySession.objects.count()

            if is_dry_run:
                self.stdout.write(f"DRY RUN: would process {len(all_records)} records")
                self.stdout.write(f"Current row count in DB: {db_count}")
                if db_count > len(all_records):
                    self.stdout.write(self.style.WARNING(
                        f"Note: DB has {db_count - len(all_records)} more rows than Airtable — "
                        f"these are records deleted in Airtable but preserved in Postgres."
                    ))
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
                f"skipped (no session_id): {stats['skipped']}"
            ))

            new_db_count = LiteracySession.objects.count()
            if new_db_count != db_count:
                self.stdout.write(f"DB row count: {db_count} → {new_db_count}")

        except Exception as e:
            if sync_log:
                try:
                    sync_log.mark_complete(success=False, error_message=str(e))
                except Exception:
                    pass
            self.stdout.write(self.style.ERROR(f"Sync failed: {e}"))
            raise

    def bulk_upsert(self, all_records):
        """
        Fetch existing session_id → pk mapping in one query.
        Split incoming records into new (bulk_create) and existing (bulk_update).
        """
        # One query to get all existing session_ids and their PKs
        existing = {
            row['session_id']: row['id']
            for row in LiteracySession.objects.values('id', 'session_id')
        }

        new_objs = []
        update_objs = []
        skipped = 0

        for record in all_records:
            fields = record.get('fields', {})
            session_id = fields.get('Sessions ID')

            if not session_id:
                skipped += 1
                continue

            row_data = self.extract_row(fields)

            if session_id in existing:
                obj = LiteracySession(id=existing[session_id], session_id=session_id, **row_data)
                update_objs.append(obj)
            else:
                new_objs.append(LiteracySession(session_id=session_id, **row_data))

        # Fields to update on existing rows (everything except session_id)
        update_fields = [
            'lc_full_name', 'child_full_name', 'school', 'grade',
            'sessions_capture_date', 'total_weekly_sessions_received', 'reading_level',
            'letters_done', 'mentor', 'site_type', 'on_the_programme',
            'month', 'week', 'month_and_year', 'created',
            'sessions_met_minimum', 'duplicate_flag', 'employee_id', 'mcode',
        ]

        with transaction.atomic():
            if new_objs:
                LiteracySession.objects.bulk_create(new_objs, batch_size=500)
            if update_objs:
                LiteracySession.objects.bulk_update(update_objs, update_fields, batch_size=500)

        return {'created': len(new_objs), 'updated': len(update_objs), 'skipped': skipped}

    def extract_row(self, fields):
        """Extract fields from one Airtable record into a dict for LiteracySession."""
        def safe_get(name, default=""):
            val = fields.get(name, default)
            if isinstance(val, list):
                return val[0] if val else default
            if isinstance(val, dict):
                return val.get('name', val.get('id', str(val)))
            return val

        def safe_array(name):
            val = fields.get(name, [])
            return val if isinstance(val, list) else []

        return dict(
            lc_full_name=safe_get('Full Name (from LC Full Name)'),
            child_full_name=safe_get('Child Full Name (from Child Full Name)'),
            school=safe_get('Schools (from Schools)'),
            grade=safe_get('Grade'),
            sessions_capture_date=parse_date(fields.get('Sessions Capture Date', '') or ''),
            total_weekly_sessions_received=fields.get('Total Weekly Sessions Received', 0),
            reading_level=fields.get('Reading Level', ''),
            letters_done=safe_array('Letters Done'),
            mentor=safe_get('Mentor'),
            site_type=safe_get('Site Type'),
            on_the_programme=safe_get('On the Programme'),
            month=safe_get('Month', '').replace('"', ''),
            week=safe_get('Week', '').replace('"', ''),
            month_and_year=safe_get('Month and Year', '').replace('"', ''),
            created=fields.get('Created'),
            sessions_met_minimum=safe_get('Sessions Met Minimum'),
            duplicate_flag=fields.get('Duplicate Flag', ''),
            employee_id=str(safe_get('Employee ID', '')),
            mcode=str(fields.get('Mcode', '')),
        )

    def fetch_from_airtable(self, base_id, table_name, token):
        url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
        headers = {"Authorization": f"Bearer {token}"}
        all_records = []

        while url:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                raise ValueError(f"Airtable API error {response.status_code}: {response.text[:200]}")
            data = response.json()
            all_records.extend(data.get('records', []))
            offset = data.get('offset')
            url = f"https://api.airtable.com/v0/{base_id}/{table_name}?offset={offset}" if offset else None

        return all_records
