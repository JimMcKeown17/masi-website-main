import os
import requests
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.db import transaction
from dotenv import load_dotenv
from api.models import Youth, School, Mentor, AirtableSyncLog


class Command(BaseCommand):
    """
    Syncs youth (literacy/numeracy coaches) from Airtable into the Youth model.

    Canonical key: employee_id (unique integer).
    Upsert key: airtable_id (Airtable record ID).
    youth_uid is derived as 'YTH-{employee_id}' — used as join key in 2026 session tables.

    FK resolution (best-effort, null on no match):
      - Site Placement (school name) → School.name
      - Mentor (mentor full name) → Mentor.name

    Run sync_airtable_staff before this command so mentor name lookups work.

    Required env vars:
      AIRTABLE_YOUTH_2026_BASE_ID
      AIRTABLE_YOUTH_2026_TABLE_ID
      AIRTABLE_TOKEN
    """
    help = "Sync youth records from Airtable into the Youth model"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Preview without saving')
        parser.add_argument('--verbose', action='store_true', help='Show sample records fetched')

    def handle(self, *args, **options):
        load_dotenv()
        base_id = os.getenv("AIRTABLE_YOUTH_2026_BASE_ID")
        table_id = os.getenv("AIRTABLE_YOUTH_2026_TABLE_ID")
        token = os.getenv("AIRTABLE_TOKEN")
        is_dry_run = options['dry_run']

        if not all([base_id, table_id, token]):
            self.stdout.write(self.style.ERROR(
                "Missing env vars. Required:\n"
                f"  AIRTABLE_YOUTH_2026_BASE_ID: {bool(base_id)}\n"
                f"  AIRTABLE_YOUTH_2026_TABLE_ID: {bool(table_id)}\n"
                f"  AIRTABLE_TOKEN: {bool(token)}"
            ))
            return

        if is_dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN MODE — no changes will be saved ===\n"))

        sync_log = None
        if not is_dry_run:
            sync_log = AirtableSyncLog.objects.create(sync_type='youth')
            self.stdout.write(f"Sync log started (ID: {sync_log.id})")

        try:
            all_records = self.fetch_from_airtable(base_id, table_id, token)
            self.stdout.write(self.style.SUCCESS(f"Fetched {len(all_records)} records from Airtable"))

            if options['verbose']:
                for r in all_records[:3]:
                    f = r['fields']
                    self.stdout.write(
                        f"  Sample: #{f.get('Employee ID')} | "
                        f"{f.get('Full Name')} | "
                        f"status={f.get('Employment Status')} | "
                        f"title={f.get('Job Title')} | "
                        f"site={f.get('Site Placement')} | "
                        f"mentor={f.get('Mentor')}"
                    )

            db_count = Youth.objects.count()

            if is_dry_run:
                self.stdout.write(f"DRY RUN: would process {len(all_records)} records")
                self.stdout.write(f"Current row count in DB: {db_count}")
                return

            # Build lookup maps for FK resolution
            school_map = {s.name.lower().strip(): s.id for s in School.objects.all()}
            mentor_map = {m.name.lower().strip(): m.id for m in Mentor.objects.all()}

            # Airtable typo aliases — map misspelled names to canonical mentor
            MENTOR_ALIASES = {
                'kariena tsaone': 'kariena tsaoane',
                'simamnkele sali': 'simamkele sali',
            }
            for alias, canonical in MENTOR_ALIASES.items():
                if canonical in mentor_map and alias not in mentor_map:
                    mentor_map[alias] = mentor_map[canonical]

            self.stdout.write(f"Loaded {len(school_map)} schools and {len(mentor_map)} mentors for FK resolution")

            stats = self.bulk_upsert(all_records, school_map, mentor_map)

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
                f"skipped: {stats['skipped']}, "
                f"school unmatched: {stats['school_unmatched']}, "
                f"mentor unmatched: {stats['mentor_unmatched']}"
            ))

        except Exception as e:
            if sync_log:
                try:
                    sync_log.mark_complete(success=False, error_message=str(e))
                except Exception:
                    pass
            self.stdout.write(self.style.ERROR(f"Sync failed: {e}"))
            raise

    def bulk_upsert(self, all_records, school_map, mentor_map):
        # Delete orphans — DB records whose airtable_id no longer exists in Airtable
        incoming_airtable_ids = {r.get('id') for r in all_records if r.get('id')}
        orphans = Youth.objects.exclude(airtable_id__isnull=True).exclude(airtable_id__in=incoming_airtable_ids)
        orphan_count = orphans.count()
        if orphan_count:
            self.stdout.write(self.style.WARNING(f"Deleting {orphan_count} orphan records not found in Airtable"))
            orphans.delete()

        # Build lookup by airtable_id AND employee_id so we match existing
        # records regardless of which key was used to create them
        existing_by_airtable = {
            row['airtable_id']: row['id']
            for row in Youth.objects.exclude(airtable_id__isnull=True)
                .values('id', 'airtable_id')
        }
        existing_by_employee = {
            row['employee_id']: row['id']
            for row in Youth.objects.values('id', 'employee_id')
        }

        new_objs = []
        update_objs = []
        skipped = 0
        school_unmatched = 0
        mentor_unmatched = 0
        seen_employee_ids = set()

        for record in all_records:
            airtable_id = record.get('id')
            if not airtable_id:
                skipped += 1
                continue

            row_data = self.extract_row(record, school_map, mentor_map)
            if row_data is None:
                skipped += 1
                continue

            # Deduplicate by employee_id — keep the first Airtable record seen
            emp_id = row_data.get('employee_id')
            if emp_id in seen_employee_ids:
                skipped += 1
                continue
            seen_employee_ids.add(emp_id)

            if row_data.pop('_school_unmatched', False):
                school_unmatched += 1
            if row_data.pop('_mentor_unmatched', False):
                mentor_unmatched += 1

            # Match by airtable_id first, then by employee_id
            existing_pk = existing_by_airtable.get(airtable_id) or existing_by_employee.get(emp_id)
            if existing_pk:
                obj = Youth(id=existing_pk, airtable_id=airtable_id, **row_data)
                update_objs.append(obj)
            else:
                new_objs.append(Youth(airtable_id=airtable_id, **row_data))

        update_fields = [
            'airtable_id', 'first_names', 'last_name', 'full_name',
            'dob', 'age', 'gender', 'race',
            'id_type', 'rsa_id_number',
            'cell_phone_number', 'email', 'emergency_number',
            'street_number', 'street_address', 'suburb_township', 'city_or_town', 'postal_code',
            'job_title', 'employment_status', 'start_date', 'end_date',
            'school_id', 'mentor_id',
        ]

        with transaction.atomic():
            if new_objs:
                Youth.objects.bulk_create(new_objs, batch_size=500)
            if update_objs:
                Youth.objects.bulk_update(update_objs, update_fields, batch_size=500)

        return {
            'created': len(new_objs),
            'updated': len(update_objs),
            'skipped': skipped,
            'school_unmatched': school_unmatched,
            'mentor_unmatched': mentor_unmatched,
        }

    def extract_row(self, record, school_map, mentor_map):
        fields = record.get('fields', {})

        def safe_first(name):
            val = fields.get(name)
            if isinstance(val, list):
                return val[0] if val else None
            return val or None

        employee_id = fields.get('Employee ID')
        if not employee_id:
            return None

        # School FK resolution by name (case-insensitive)
        site_name = safe_first('Site Placement')
        school_id = None
        school_unmatched = False
        if site_name:
            school_id = school_map.get(site_name.lower().strip())
            if school_id is None:
                school_unmatched = True

        # Mentor FK resolution by name (case-insensitive)
        mentor_name = safe_first('Mentor')
        mentor_id = None
        mentor_unmatched = False
        if mentor_name:
            mentor_id = mentor_map.get(mentor_name.lower().strip())
            if mentor_id is None:
                mentor_unmatched = True

        return dict(
            employee_id=employee_id,
            youth_uid=f"YTH-{employee_id}",
            first_names=fields.get('First Names') or '',
            last_name=fields.get('Last Name') or '',
            full_name=fields.get('Full Name') or '',
            dob=parse_date(fields.get('DOB', '') or ''),
            age=fields.get('Age'),
            gender=fields.get('Gender'),
            race=fields.get('Race'),
            id_type=fields.get('ID Type'),
            rsa_id_number=fields.get('RSA ID Number'),
            cell_phone_number=fields.get('Cell Phone Number'),
            email=fields.get('Email') or None,
            emergency_number=fields.get('Emergency Number'),
            street_number=fields.get('Street Number'),
            street_address=fields.get('Street Address'),
            suburb_township=fields.get('Suburb/Township'),
            city_or_town=fields.get('City or Town'),
            postal_code=str(fields.get('Postal Code', '') or '').strip() or None,
            job_title=safe_first('Job Title'),
            employment_status=safe_first('Employment Status') or 'Active',
            start_date=parse_date(safe_first('Start Date') or ''),
            end_date=parse_date(safe_first('End Date') or ''),
            school_id=school_id,
            mentor_id=mentor_id,
            _school_unmatched=school_unmatched,
            _mentor_unmatched=mentor_unmatched,
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
