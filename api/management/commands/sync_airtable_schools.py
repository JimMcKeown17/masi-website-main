import os
import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from dotenv import load_dotenv
from api.models import School, AirtableSyncLog


# Map Airtable Type values to Django SCHOOL_TYPE_CHOICES keys
SCHOOL_TYPE_MAP = {
    'ECD': 'ECDC',
    'Primary': 'Primary School',
    'High School': 'Secondary School',
}


class Command(BaseCommand):
    """
    Syncs schools from the Airtable schools database into the School model.

    Upsert key: airtable_id (Airtable record ID).
    324 of 326 existing Postgres records already match the new base by record ID.

    Fields synced from the new Airtable table:
      name, type, school_uid, school_number, suburb, latitude, longitude

    Fields NOT in the new Airtable table (preserved as-is in Postgres):
      contact_phone, contact_email, contact_person, principal, city, address,
      site_type, actively_working_in

    Required env vars:
      AIRTABLE_SCHOOLS_BASE_ID
      AIRTABLE_SCHOOLS_TABLE_ID
      AIRTABLE_TOKEN
    """
    help = "Sync schools from Airtable using bulk upsert"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Preview without saving')
        parser.add_argument('--verbose', action='store_true', help='Show sample records fetched')

    def handle(self, *args, **options):
        load_dotenv()
        base_id = os.getenv("AIRTABLE_SCHOOLS_BASE_ID")
        table_id = os.getenv("AIRTABLE_SCHOOLS_TABLE_ID")
        token = os.getenv("AIRTABLE_TOKEN")
        is_dry_run = options['dry_run']

        if not all([base_id, table_id, token]):
            self.stdout.write(self.style.ERROR(
                "Missing env vars. Required:\n"
                f"  AIRTABLE_SCHOOLS_BASE_ID: {bool(base_id)}\n"
                f"  AIRTABLE_SCHOOLS_TABLE_ID: {bool(table_id)}\n"
                f"  AIRTABLE_TOKEN: {bool(token)}"
            ))
            return

        if is_dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN MODE — no changes will be saved ===\n"))

        sync_log = None
        if not is_dry_run:
            sync_log = AirtableSyncLog.objects.create(sync_type='schools')
            self.stdout.write(f"Sync log started (ID: {sync_log.id})")

        try:
            all_records = self.fetch_from_airtable(base_id, table_id, token)
            self.stdout.write(self.style.SUCCESS(f"Fetched {len(all_records)} records from Airtable"))

            if options['verbose']:
                for r in all_records[:3]:
                    f = r['fields']
                    self.stdout.write(
                        f"  Sample: {f.get('School UID')} | "
                        f"{f.get('School')} | "
                        f"type={f.get('Type')} | "
                        f"suburb={f.get('Suburb')}"
                    )

            db_count = School.objects.count()

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
            row['airtable_id']: row['id']
            for row in School.objects.exclude(airtable_id__isnull=True).values('id', 'airtable_id')
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
                skipped += 1
                continue

            if airtable_id in existing:
                obj = School(id=existing[airtable_id], airtable_id=airtable_id, **row_data)
                update_objs.append(obj)
            else:
                new_objs.append(School(airtable_id=airtable_id, **row_data))

        update_fields = [
            'name', 'type', 'school_uid', 'school_number', 'suburb',
            'latitude', 'longitude',
        ]

        with transaction.atomic():
            if new_objs:
                School.objects.bulk_create(new_objs, batch_size=500)
            if update_objs:
                School.objects.bulk_update(update_objs, update_fields, batch_size=500)

        return {'created': len(new_objs), 'updated': len(update_objs), 'skipped': skipped}

    def extract_row(self, record):
        fields = record.get('fields', {})

        name = fields.get('School')
        if not name:
            return None

        type_raw = fields.get('Type', [])
        if isinstance(type_raw, list) and type_raw:
            school_type = SCHOOL_TYPE_MAP.get(type_raw[0])
        else:
            school_type = None

        return dict(
            name=name,
            type=school_type,
            school_uid=fields.get('School UID'),
            school_number=fields.get('School Number'),
            suburb=fields.get('Suburb'),
            latitude=fields.get('Coord East'),
            longitude=fields.get('Coord South'),
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
