import os
import requests
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.db import transaction
from dotenv import load_dotenv
from api.models import NumeracySessionChild, AirtableSyncLog


class Command(BaseCommand):
    """
    Syncs numeracy session data from Airtable into NumeracySessionChild.

    GRAIN: One Airtable session row can have multiple children linked to it.
    We expand those into one Postgres row per (session, child) combination.
    The compound key (source_airtable_id, child_name) uniquely identifies each row.

    FIRST RUN AFTER MIGRATION: Use --initial-load once.
    This clears old rows (source_airtable_id=NULL) and bulk-inserts everything fresh.
    Fast because it uses bulk_create instead of row-by-row queries.

    NORMAL NIGHTLY RUNS: No flag needed.
    Fetches existing (source_airtable_id, child_name) pairs from DB in one query,
    then bulk-creates new rows and bulk-updates changed rows. No full delete.
    """
    help = "Sync numeracy session data from Airtable using bulk upsert (never wipes the table)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Preview what would change without saving'
        )
        parser.add_argument(
            '--verbose', action='store_true',
            help='Show summary stats per batch'
        )
        parser.add_argument(
            '--initial-load', action='store_true',
            help=(
                'ONE-TIME USE after source_airtable_id migration. '
                'Deletes all rows with source_airtable_id=NULL and bulk-inserts fresh. '
                'After this, use normal runs.'
            )
        )

    def handle(self, *args, **options):
        load_dotenv()
        base_id = os.getenv("AIRTABLE_NUMERACY_SESSIONS_BASE_ID")
        table_name = os.getenv("AIRTABLE_NUMERACY_DAILY_SESSIONS_TABLE_NAME")
        token = os.getenv("AIRTABLE_TOKEN")
        is_dry_run = options['dry_run']
        is_initial_load = options['initial_load']

        if not all([base_id, table_name, token]):
            self.stdout.write(self.style.ERROR("Missing Airtable credentials in environment variables"))
            return

        if is_dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN MODE — no changes will be saved ===\n"))

        null_id_count = NumeracySessionChild.objects.filter(source_airtable_id__isnull=True).count()
        if null_id_count > 0 and not is_initial_load and not is_dry_run:
            self.stdout.write(self.style.WARNING(
                f"WARNING: {null_id_count} rows have source_airtable_id=NULL (pre-migration rows). "
                f"Run with --initial-load once to clear them."
            ))

        sync_log = None
        if not is_dry_run:
            sync_log = AirtableSyncLog.objects.create(sync_type='numeracy_sessions')
            self.stdout.write(f"Sync log started (ID: {sync_log.id})")

        try:
            all_records = self.fetch_from_airtable(base_id, table_name, token)
            self.stdout.write(self.style.SUCCESS(f"Fetched {len(all_records)} Airtable records"))

            expanded_rows = self.expand_to_child_rows(all_records)
            self.stdout.write(f"Expanded to {len(expanded_rows)} child-level rows")

            if is_dry_run:
                self.stdout.write(f"\nDRY RUN: would process {len(expanded_rows)} rows")
                self.stdout.write(f"Current row count in DB: {NumeracySessionChild.objects.count()}")
                self.stdout.write(f"Rows with NULL source_airtable_id (pre-migration): {null_id_count}")
                return

            if is_initial_load:
                stats = self.initial_load(expanded_rows)
            else:
                stats = self.bulk_upsert(expanded_rows)

            if sync_log:
                sync_log.records_processed = len(expanded_rows)
                sync_log.records_created = stats['created']
                sync_log.records_updated = stats['updated']
                sync_log.records_skipped = stats['skipped']
                sync_log.mark_complete(success=True)

            self.stdout.write(self.style.SUCCESS(
                f"\nSync complete — "
                f"Airtable records: {len(all_records)}, "
                f"expanded rows: {len(expanded_rows)}, "
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

    def initial_load(self, expanded_rows):
        """
        ONE-TIME operation after adding source_airtable_id to the model.
        Deletes all rows that predate this migration (source_airtable_id=NULL),
        then bulk-inserts everything fresh with source_airtable_id populated.
        Uses bulk_create so it's fast — a few DB round-trips instead of 15,000.
        """
        with transaction.atomic():
            deleted_count, _ = NumeracySessionChild.objects.filter(
                source_airtable_id__isnull=True
            ).delete()
            self.stdout.write(self.style.WARNING(
                f"Initial load: deleted {deleted_count} pre-migration rows"
            ))

            objs = [NumeracySessionChild(**row) for row in expanded_rows]
            NumeracySessionChild.objects.bulk_create(objs, batch_size=500)
            self.stdout.write(self.style.SUCCESS(
                f"Initial load: inserted {len(objs)} rows with source_airtable_id populated"
            ))

        return {'created': len(expanded_rows), 'updated': 0, 'skipped': 0}

    def bulk_upsert(self, expanded_rows):
        """
        Normal nightly sync. Fetches existing (source_airtable_id, child_name) pairs
        from DB in one query, then bulk-creates new rows and bulk-updates changed rows.
        Much faster than row-by-row update_or_create over a remote connection.
        """
        # Build a lookup map of what already exists in the DB
        # key: (source_airtable_id, child_name), value: pk
        existing = {
            (row['source_airtable_id'], row['child_name']): row['id']
            for row in NumeracySessionChild.objects.filter(
                source_airtable_id__isnull=False
            ).values('id', 'source_airtable_id', 'child_name')
        }

        new_objs = []
        update_objs = []
        skipped = 0

        for row in expanded_rows:
            airtable_id = row.get('source_airtable_id')
            if not airtable_id:
                skipped += 1
                continue

            child_name = row.get('child_name')
            key = (airtable_id, child_name)

            if key in existing:
                obj = NumeracySessionChild(id=existing[key], **row)
                update_objs.append(obj)
            else:
                new_objs.append(NumeracySessionChild(**row))

        # Fields to update on existing rows (everything except the key fields)
        update_fields = [
            'session_id', 'nc_full_name', 'numeracy_site', 'sessions_capture_date',
            'children_in_group', 'created', 'current_count_level', 'baseline_count_level',
            'number_recognition', 'month', 'week', 'month_and_year',
            'site_placement', 'employee_id', 'mentor', 'employment_status', 'duplicate_flag',
        ]

        with transaction.atomic():
            if new_objs:
                NumeracySessionChild.objects.bulk_create(new_objs, batch_size=500)
            if update_objs:
                NumeracySessionChild.objects.bulk_update(update_objs, update_fields, batch_size=500)

        return {'created': len(new_objs), 'updated': len(update_objs), 'skipped': skipped}

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

    def expand_to_child_rows(self, records):
        """
        Expand Airtable records into child-level rows.
        One Airtable session with 3 children becomes 3 rows.
        One Airtable session with no children becomes 1 row with child_name=None.
        """
        rows = []
        for record in records:
            airtable_id = record.get('id')
            fields = record.get('fields', {})

            def safe_get(name, default=""):
                val = fields.get(name, default)
                if isinstance(val, list):
                    return val[0] if val else default
                return val

            def safe_array(name):
                val = fields.get(name, [])
                return val if isinstance(val, list) else []

            base = dict(
                source_airtable_id=airtable_id,
                session_id=fields.get('Session ID'),
                nc_full_name=safe_get('Name (from NC Full Name)'),
                numeracy_site=safe_get('Site Name (from Numeracy Sites)'),
                sessions_capture_date=parse_date(fields.get('Sessions Capture Date', '') or ''),
                children_in_group=fields.get('Children In Group', 0),
                created=fields.get('Created'),
                current_count_level=safe_get('Current Count Level'),
                baseline_count_level=safe_array('Basline Count Level'),
                number_recognition=safe_get('Number Recognition'),
                month=str(safe_get('Month')).replace('"', ''),
                week=str(safe_get('Week')).replace('"', ''),
                month_and_year=str(safe_get('Month and Year')).replace('"', ''),
                site_placement=safe_get('Site Placement'),
                employee_id=str(safe_get('Employee ID')),
                mentor=safe_get('Mentor'),
                employment_status=safe_get('Employment Status'),
                duplicate_flag=safe_get('Duplicate Flag'),
            )

            child_names = safe_array('Learner Full Name (from Children in Session)')

            if not child_names:
                rows.append({**base, 'child_name': None})
            else:
                for child in child_names:
                    rows.append({**base, 'child_name': child})

        return rows
