import os
import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from dotenv import load_dotenv
from api.models import Staff, AirtableSyncLog


class Command(BaseCommand):
    """
    Syncs staff HR records from Airtable into the Staff model.

    319 staff records covering current and former staff/mentors.
    Canonical key: employee_number (unique integer).
    Upsert key: source_airtable_id.

    Does NOT touch the User FK — that is managed separately for
    dashboard login access and is not part of the HR sync.

    Required env vars:
      AIRTABLE_STAFF_2026_BASE_ID
      AIRTABLE_STAFF_2026_TABLE_ID
      AIRTABLE_TOKEN
    """
    help = "Sync staff HR records from Airtable into the Staff model"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Preview without saving')
        parser.add_argument('--verbose', action='store_true', help='Show sample records fetched')

    def handle(self, *args, **options):
        load_dotenv()
        base_id = os.getenv("AIRTABLE_STAFF_2026_BASE_ID")
        table_id = os.getenv("AIRTABLE_STAFF_2026_TABLE_ID")
        token = os.getenv("AIRTABLE_TOKEN")
        is_dry_run = options['dry_run']

        if not all([base_id, table_id, token]):
            self.stdout.write(self.style.ERROR(
                "Missing env vars. Required:\n"
                f"  AIRTABLE_STAFF_2026_BASE_ID: {bool(base_id)}\n"
                f"  AIRTABLE_STAFF_2026_TABLE_ID: {bool(table_id)}\n"
                f"  AIRTABLE_TOKEN: {bool(token)}"
            ))
            return

        if is_dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN MODE — no changes will be saved ===\n"))

        sync_log = None
        if not is_dry_run:
            sync_log = AirtableSyncLog.objects.create(sync_type='staff')
            self.stdout.write(f"Sync log started (ID: {sync_log.id})")

        try:
            all_records = self.fetch_from_airtable(base_id, table_id, token)
            self.stdout.write(self.style.SUCCESS(f"Fetched {len(all_records)} records from Airtable"))

            if options['verbose']:
                for r in all_records[:3]:
                    f = r['fields']
                    self.stdout.write(
                        f"  Sample: #{f.get('Employee Number')} | "
                        f"{f.get('Full Name')} | "
                        f"{f.get('Gender')} | "
                        f"email={f.get('Email')}"
                    )

            db_count = Staff.objects.count()

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
            for row in Staff.objects.exclude(source_airtable_id__isnull=True)
                .values('id', 'source_airtable_id')
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
                obj = Staff(id=existing[airtable_id], source_airtable_id=airtable_id, **row_data)
                update_objs.append(obj)
            else:
                new_objs.append(Staff(source_airtable_id=airtable_id, **row_data))

        update_fields = [
            'employee_number', 'name', 'first_names', 'last_name',
            'gender', 'race', 'date_of_birth', 'id_number', 'identification_type',
            'drivers_license_code', 'cell_number', 'email', 'emergency_cell_number',
            'unit_number', 'complex_name', 'street_number', 'street',
            'suburb', 'city', 'postal_code',
        ]

        with transaction.atomic():
            if new_objs:
                Staff.objects.bulk_create(new_objs, batch_size=500)
            if update_objs:
                Staff.objects.bulk_update(update_objs, update_fields, batch_size=500)

        return {'created': len(new_objs), 'updated': len(update_objs), 'skipped': skipped}

    def extract_row(self, record):
        fields = record.get('fields', {})

        employee_number = fields.get('Employee Number')
        full_name = fields.get('Full Name')
        if not full_name:
            return None

        dob_raw = fields.get('Date of Birth')
        dob = None
        if dob_raw:
            for fmt in ('%Y/%m/%d', '%Y-%m-%d'):
                try:
                    dob = datetime.strptime(dob_raw, fmt).date()
                    break
                except (ValueError, AttributeError):
                    continue

        return dict(
            employee_number=employee_number,
            name=full_name,
            first_names=fields.get('First Names'),
            last_name=fields.get('Last Name'),
            gender=fields.get('Gender'),
            race=fields.get('Race'),
            date_of_birth=dob,
            id_number=fields.get('ID Number'),
            identification_type=fields.get('Identification Type'),
            drivers_license_code=fields.get('Drivers License Code'),
            cell_number=fields.get('Cell Number'),
            email=fields.get('Email') or None,
            emergency_cell_number=fields.get('Emergency Cell Number'),
            unit_number=fields.get('Unit number'),
            complex_name=fields.get('Complex'),
            street_number=fields.get('Street number'),
            street=fields.get('Street'),
            suburb=fields.get('Suburb or district'),
            city=fields.get('City or town'),
            postal_code=str(fields.get('Postal Code', '') or '').strip() or None,
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
