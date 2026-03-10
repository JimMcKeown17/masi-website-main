import os
import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from dotenv import load_dotenv
from api.models import CanonicalChild, AirtableSyncLog


class Command(BaseCommand):
    """
    Syncs the master Airtable children table into CanonicalChild.

    One row per child. Uses source_airtable_id as the upsert key.
    Also enforces uniqueness on mcode and child_uid.

    This table is the stable cross-year identity record for all children on
    the programme. The child_uid (CH-XXXXX) is referenced by 2026 session tables.

    Required env vars:
      AIRTABLE_CHILDREN_2026_BASE_ID   = app6ayjg1NwvYdZQf
      AIRTABLE_CHILDREN_2026_TABLE_ID  = tbleBg6n4f3dcJ8vJ
      AIRTABLE_TOKEN
    """
    help = "Sync canonical children from the master Airtable children table"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Preview without saving')
        parser.add_argument('--verbose', action='store_true', help='Show sample records fetched')

    def handle(self, *args, **options):
        load_dotenv()
        base_id = os.getenv("AIRTABLE_CHILDREN_2026_BASE_ID")
        table_id = os.getenv("AIRTABLE_CHILDREN_2026_TABLE_ID")
        token = os.getenv("AIRTABLE_TOKEN")
        is_dry_run = options['dry_run']

        if not all([base_id, table_id, token]):
            self.stdout.write(self.style.ERROR(
                "Missing env vars. Required:\n"
                f"  AIRTABLE_CHILDREN_2026_BASE_ID: {bool(base_id)}\n"
                f"  AIRTABLE_CHILDREN_2026_TABLE_ID: {bool(table_id)}\n"
                f"  AIRTABLE_TOKEN: {bool(token)}"
            ))
            return

        if is_dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN MODE — no changes will be saved ===\n"))

        sync_log = None
        if not is_dry_run:
            sync_log = AirtableSyncLog.objects.create(sync_type='canonical_children')
            self.stdout.write(f"Sync log started (ID: {sync_log.id})")

        try:
            all_records = self.fetch_from_airtable(base_id, table_id, token)
            self.stdout.write(self.style.SUCCESS(f"Fetched {len(all_records)} records from Airtable"))

            if options['verbose']:
                for r in all_records[:3]:
                    f = r['fields']
                    self.stdout.write(
                        f"  Sample: {f.get('Child UID')} | "
                        f"mcode={f.get('Mcode')} | "
                        f"{f.get('Canonical Full Name')} | "
                        f"years={f.get('Years')} | "
                        f"school_2025={f.get('2025 School')}"
                    )

            db_count = CanonicalChild.objects.count()

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
            for row in CanonicalChild.objects.values('id', 'source_airtable_id')
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
            if row_data is None:
                # extract_row returns None when required fields are missing
                skipped += 1
                continue

            if airtable_id in existing:
                obj = CanonicalChild(id=existing[airtable_id], source_airtable_id=airtable_id, **row_data)
                update_objs.append(obj)
            else:
                new_objs.append(CanonicalChild(source_airtable_id=airtable_id, **row_data))

        update_fields = [
            'child_uid', 'mcode', 'first_name', 'surname', 'full_name',
            'gender', 'identity_confidence', 'years_active', 'programme',
            'school_2025', 'grade_2025', 'created_in_airtable',
        ]

        with transaction.atomic():
            if new_objs:
                CanonicalChild.objects.bulk_create(new_objs, batch_size=500)
            if update_objs:
                CanonicalChild.objects.bulk_update(update_objs, update_fields, batch_size=500)

        return {'created': len(new_objs), 'updated': len(update_objs), 'skipped': skipped}

    def extract_row(self, record):
        fields = record.get('fields', {})

        mcode = fields.get('Mcode')
        child_uid = fields.get('Child UID')

        # Both mcode and child_uid are required for a useful canonical record
        if not mcode or not child_uid:
            return None

        created_raw = fields.get('Created')
        created_dt = None
        if created_raw:
            try:
                created_dt = datetime.fromisoformat(created_raw.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass

        years = fields.get('Years', [])
        if not isinstance(years, list):
            years = []

        programme = fields.get('Programme Belonging', [])
        if not isinstance(programme, list):
            programme = [programme] if programme else []

        return dict(
            child_uid=child_uid,
            mcode=int(mcode),
            first_name=fields.get('Canonical First Name'),
            surname=fields.get('Canonical Surname'),
            full_name=fields.get('Canonical Full Name'),
            gender=fields.get('Gender'),
            identity_confidence=fields.get('Identity Confidence'),
            years_active=years,
            programme=programme,
            school_2025=fields.get('2025 School'),
            grade_2025=fields.get('2025 Grade'),
            created_in_airtable=created_dt,
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
