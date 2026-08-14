import os
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db import transaction
from dotenv import load_dotenv
from api.models import LiteracySession2026, Youth, School, CanonicalChild
from api.airtable_sync import fetch_airtable_records, run_session_import


SYNC_TYPE = 'literacy_sessions_2026'
AIRTABLE_FIELDS = [
    'Session Record', 'Session UID', 'Session Date', 'Youth UID', 'School UID',
    'Child UID', 'Unique Child Selected List', 'Sounds Covered',
    'Sounds Covered (Clean)', 'Blending Level', 'Duplicate?',
    'Overall Session Status', 'Capture Delay', 'Capture Delay Flag',
    'Duplicate Fingerprint', 'Created',
]


class Command(BaseCommand):
    """
    Syncs 2026 literacy session data from Airtable into LiteracySession2026.

    The 2026 table uses UIDs (YTH-XXXX, SCH-XXXXX, CH-XXXXX) for cross-table
    references instead of text names. These will eventually FK to canonical tables.

    Grain: one Airtable record = one Postgres row.
    Each session involves exactly 2 children (child_uid_1, child_uid_2).

    Upsert key: source_airtable_id (unique Airtable record ID).
    Uses bulk operations for performance.

    Required env vars:
      AIRTABLE_LITERACY_2026_BASE_ID   = apppvs3MhpQvVNnDT
      AIRTABLE_LITERACY_2026_TABLE_ID  = tblw7FP4NT0oM6U9p
      AIRTABLE_TOKEN
    """
    help = "Sync 2026 literacy session data from Airtable"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Preview without saving')
        parser.add_argument('--verbose', action='store_true', help='Show first few records fetched')
        parser.add_argument(
            '--incremental-new',
            action='store_true',
            help='Upsert only Airtable records created since the acknowledged cursor',
        )

    def handle(self, *args, **options):
        load_dotenv()
        base_id = os.getenv("AIRTABLE_LITERACY_2026_BASE_ID")
        table_id = os.getenv("AIRTABLE_LITERACY_2026_TABLE_ID")
        token = os.getenv("AIRTABLE_TOKEN")
        is_dry_run = options['dry_run']

        if not all([base_id, table_id, token]):
            self.stdout.write(self.style.ERROR(
                "Missing env vars. Required:\n"
                f"  AIRTABLE_LITERACY_2026_BASE_ID: {bool(base_id)}\n"
                f"  AIRTABLE_LITERACY_2026_TABLE_ID: {bool(table_id)}\n"
                f"  AIRTABLE_TOKEN: {bool(token)}"
            ))
            return

        # Build FK lookup dicts for resolving UIDs to canonical records
        self.youth_by_uid = {y.youth_uid: y for y in Youth.objects.filter(youth_uid__isnull=False)}
        self.school_by_uid = {s.school_uid: s for s in School.objects.filter(school_uid__isnull=False)}
        self.child_by_uid = {c.child_uid: c for c in CanonicalChild.objects.all()}
        self.stdout.write(f"FK lookups: youth={len(self.youth_by_uid)}, school={len(self.school_by_uid)}, child={len(self.child_by_uid)}")

        def show_samples(records):
            if options['verbose']:
                for r in records:
                    self.stdout.write(f"  Sample: {r['fields'].get('Session UID')} | "
                                      f"{r['fields'].get('Session Date')} | "
                                      f"youth={r['fields'].get('Youth UID')} | "
                                      f"school={r['fields'].get('School UID')} | "
                                      f"children={r['fields'].get('Child UID')}")

        run_session_import(
            self,
            sync_type=SYNC_TYPE,
            model=LiteracySession2026,
            base_id=base_id,
            table_id=table_id,
            token=token,
            fields=AIRTABLE_FIELDS,
            incremental_new=options['incremental_new'],
            dry_run=is_dry_run,
            upper_bound=timezone.now(),
            fetcher=fetch_airtable_records,
            verbose_callback=show_samples,
        )

    def bulk_upsert(self, all_records):
        """
        Fetch existing source_airtable_ids in one query.
        Split into new (bulk_create) and existing (bulk_update).
        """
        incoming_ids = [record.get('id') for record in all_records if record.get('id')]
        existing = {
            row['source_airtable_id']: row['id']
            for row in LiteracySession2026.objects.filter(
                source_airtable_id__in=incoming_ids
            ).values('id', 'source_airtable_id')
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
                obj = LiteracySession2026(id=existing[airtable_id], source_airtable_id=airtable_id, **row_data)
                update_objs.append(obj)
            else:
                new_objs.append(LiteracySession2026(source_airtable_id=airtable_id, **row_data))

        update_fields = [
            'session_record', 'session_uid', 'session_date',
            'youth_uid', 'school_uid', 'child_uid_1', 'child_uid_2', 'child_names',
            'youth_id', 'school_id', 'child_1_id', 'child_2_id',
            'sounds_covered', 'sounds_covered_clean', 'blending_level',
            'duplicate_status', 'overall_session_status',
            'capture_delay', 'capture_delay_flag', 'duplicate_fingerprint',
            'created_in_airtable',
        ]

        with transaction.atomic():
            if new_objs:
                LiteracySession2026.objects.bulk_create(new_objs, batch_size=500)
            if update_objs:
                LiteracySession2026.objects.bulk_update(update_objs, update_fields, batch_size=500)

        return {'created': len(new_objs), 'updated': len(update_objs), 'skipped': skipped}

    def extract_row(self, record):
        """Extract fields from one Airtable record into a LiteracySession2026 dict."""
        fields = record.get('fields', {})

        def safe_first(name):
            """Get first element of a lookup array, or empty string."""
            val = fields.get(name)
            if isinstance(val, list):
                return val[0] if val else None
            return val or None

        def strip_emoji(val):
            """Strip leading emoji from status strings like '🟢 Unique' → 'Unique'."""
            if not val:
                return val
            # Remove leading non-ASCII characters and strip
            return val.encode('ascii', 'ignore').decode().strip(' -')

        child_uids = fields.get('Child UID', [])
        child_uid_1 = child_uids[0] if len(child_uids) > 0 else None
        child_uid_2 = child_uids[1] if len(child_uids) > 1 else None

        created_raw = fields.get('Created')
        created_dt = None
        if created_raw:
            try:
                created_dt = datetime.fromisoformat(created_raw.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass

        youth_uid_val = safe_first('Youth UID')
        school_uid_val = safe_first('School UID')

        return dict(
            session_record=fields.get('Session Record'),
            session_uid=fields.get('Session UID'),
            session_date=parse_date(fields.get('Session Date', '') or ''),
            youth_uid=youth_uid_val,
            school_uid=school_uid_val,
            child_uid_1=child_uid_1,
            child_uid_2=child_uid_2,
            youth=self.youth_by_uid.get(youth_uid_val),
            school=self.school_by_uid.get(school_uid_val),
            child_1=self.child_by_uid.get(child_uid_1),
            child_2=self.child_by_uid.get(child_uid_2),
            child_names=fields.get('Unique Child Selected List'),
            sounds_covered=fields.get('Sounds Covered'),
            sounds_covered_clean=fields.get('Sounds Covered (Clean)'),
            blending_level=fields.get('Blending Level'),
            duplicate_status=strip_emoji(safe_first('Duplicate?')),
            overall_session_status=strip_emoji(fields.get('Overall Session Status')),
            capture_delay=fields.get('Capture Delay'),
            capture_delay_flag=strip_emoji(fields.get('Capture Delay Flag')),
            duplicate_fingerprint=fields.get('Duplicate Fingerprint'),
            created_in_airtable=created_dt,
        )

    def fetch_from_airtable(self, base_id, table_id, token):
        """Compatibility wrapper for scripts that called the old command method."""
        return fetch_airtable_records(
            base_id=base_id,
            table_id=table_id,
            token=token,
            fields=AIRTABLE_FIELDS,
        )
