import os
import requests
from copy import deepcopy

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date
from django.db import transaction
from dotenv import load_dotenv
from api.models import Youth, School, Mentor, AirtableSyncLog


SUBSIDY_ENRICHMENT_CONTRACT = "youth_subsidy_enrichment_v1"
COMBINED_LINK_FIELD = "Combined Youth Data"
SUBSIDY_FIELD_MAP = {
    "Funder": "Funder",
    "SEF (Current Status)": "SEF (Current Status) (from Office Link)",
    "SEF Start Date": "SEF Start Date (from Office Link)",
    "SEF End Date": "SEF End Date (from Office Link)",
}
SUBSIDY_FIELDS = tuple(SUBSIDY_FIELD_MAP)
BASIC_FIELDS = (
    "Employee ID",
    "First Names",
    "Last Name",
    "Full Name",
    "DOB",
    "Age",
    "Gender",
    "Race",
    "ID Type",
    "RSA ID Number",
    "Cell Phone Number",
    "Email",
    "Emergency Number",
    "Street Number",
    "Street Address",
    "Suburb/Township",
    "City or Town",
    "Postal Code",
    "Job Title",
    "Employment Status",
    "Start Date",
    "End Date",
    "Site Placement",
    "Mentor",
    COMBINED_LINK_FIELD,
)


def _coerce_int(value):
    """Coerce an Airtable field value to an int, or None.

    Airtable formula/computed fields (e.g. Age, derived from DOB) return the
    sentinel {'specialValue': 'NaN'} / {'specialValue': 'Infinity'} -- a dict --
    when they can't produce a finite number (blank/invalid DOB). That dict is
    truthy, so it slips past `if not value` and `or None` guards and then
    explodes when written to an IntegerField. Real numbers and numeric strings
    coerce; anything else (the sentinel dict, blank, NaN/inf, non-numeric) -> None.
    """
    if value is None or isinstance(value, dict):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n != n or n in (float("inf"), float("-inf")):  # NaN or +/-Infinity
        return None
    return int(n)


def build_school_map():
    """name (lowered, stripped) -> School.id, preferring the canonical row.

    School has legacy duplicate rows: same name, but is_active=False and no
    school_uid, left over from earlier imports (e.g. Lingelethu exists as both
    id=1 legacy and id=184 SCH-00322). A plain dict comprehension let whichever
    row the unordered queryset yielded LAST win, so youth were sometimes attached
    to dead rows the grid never reads -- the staffing board then showed fake
    vacancies at schools that were actually staffed (bug found 2026-07-27).

    Preference order per name: active over inactive, then has school_uid, then
    highest id (newest). Deterministic, so every sync run agrees.
    """
    best = {}  # name key -> (rank, school_id)
    for school in School.objects.all().only("id", "name", "is_active", "school_uid"):
        if not school.name or not school.name.strip():
            continue
        key = school.name.lower().strip()
        rank = (school.is_active, bool(school.school_uid), school.id)
        if key not in best or rank > best[key][0]:
            best[key] = (rank, school.id)
    return {key: school_id for key, (_, school_id) in best.items()}


class Command(BaseCommand):
    """
    Syncs youth (literacy/numeracy coaches) from Airtable into the Youth model.

    Canonical key: employee_id (unique integer).
    Upsert key: airtable_id (Airtable record ID).
    youth_uid is derived as 'YTH-{employee_id}', used as join key in 2026 session tables.

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
        combined_table_id = os.getenv("AIRTABLE_COMBINED_YOUTH_DATA_TABLE_ID")
        token = os.getenv("AIRTABLE_TOKEN") or os.getenv("AIRTABLE_API_KEY")
        is_dry_run = options['dry_run']

        if not all([base_id, table_id, token]):
            message = (
                "Missing env vars. Required:\n"
                f"  AIRTABLE_YOUTH_2026_BASE_ID: {bool(base_id)}\n"
                f"  AIRTABLE_YOUTH_2026_TABLE_ID: {bool(table_id)}\n"
                f"  AIRTABLE_TOKEN or AIRTABLE_API_KEY: {bool(token)}"
            )
            if not is_dry_run:
                log = AirtableSyncLog.objects.create(
                    sync_type='youth',
                    details={
                        "subsidy_enrichment": {
                            "contract_version": SUBSIDY_ENRICHMENT_CONTRACT,
                            "command": "sync_airtable_youth",
                            "complete": False,
                            "configuration_valid": False,
                        }
                    },
                )
                log.mark_complete(success=False, error_message=message)
            raise CommandError(message)

        if is_dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN MODE: no changes will be saved ===\n"))

        sync_log = None
        if not is_dry_run:
            sync_log = AirtableSyncLog.objects.create(
                sync_type='youth',
                details={
                    "subsidy_enrichment": {
                        "contract_version": SUBSIDY_ENRICHMENT_CONTRACT,
                        "command": "sync_airtable_youth",
                        "canonical_table_id": table_id,
                        "combined_table_id": combined_table_id,
                        "complete": False,
                    }
                },
            )
            self.stdout.write(f"Sync log started (ID: {sync_log.id})")

        try:
            basic_records = self.fetch_from_airtable(
                base_id,
                table_id,
                token,
                fields=BASIC_FIELDS,
            )
            if not basic_records:
                raise CommandError(
                    "Canonical Youth Basic Data fetch returned zero records; "
                    "refusing to calculate orphan deletes."
                )
            self.stdout.write(self.style.SUCCESS(
                f"Fetched {len(basic_records)} canonical Youth Basic Data records"
            ))

            enrichment_error = None
            combined_records = []
            if not combined_table_id:
                enrichment_error = (
                    "AIRTABLE_COMBINED_YOUTH_DATA_TABLE_ID is not configured."
                )
            else:
                try:
                    combined_records = self.fetch_from_airtable(
                        base_id,
                        combined_table_id,
                        token,
                        fields=SUBSIDY_FIELDS,
                    )
                except Exception as exc:
                    enrichment_error = str(exc)

            all_records, enrichment = self.enrich_subsidies(
                basic_records,
                combined_records,
                error=enrichment_error,
            )
            enrichment.update({
                "contract_version": SUBSIDY_ENRICHMENT_CONTRACT,
                "command": "sync_airtable_youth",
                "canonical_table_id": table_id,
                "combined_table_id": combined_table_id,
                "basic_fetched": len(basic_records),
                "combined_fetched": len(combined_records),
            })

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

            # Build lookup maps for FK resolution
            school_map = build_school_map()
            mentor_map = {m.name.lower().strip(): m.id for m in Mentor.objects.all()}

            # Airtable typo aliases map misspelled names to canonical mentor.
            MENTOR_ALIASES = {
                'kariena tsaone': 'kariena tsaoane',
                'simamnkele sali': 'simamkele sali',
            }
            for alias, canonical in MENTOR_ALIASES.items():
                if canonical in mentor_map and alias not in mentor_map:
                    mentor_map[alias] = mentor_map[canonical]

            self.stdout.write(f"Loaded {len(school_map)} schools and {len(mentor_map)} mentors for FK resolution")

            stats = self.bulk_upsert(
                all_records,
                school_map,
                mentor_map,
                publish_subsidies=enrichment["complete"],
                dry_run=is_dry_run,
            )

            summary = (
                f"records: {len(all_records)}, created: {stats['created']}, "
                f"updated: {stats['updated']}, skipped: {stats['skipped']}, "
                f"orphan deletes: {stats['deleted']}, "
                f"enrichment matched: {enrichment['matched']}, "
                f"missing links: {enrichment['missing_link']}, "
                f"multiple links: {enrichment['multiple_links']}, "
                f"missing targets: {enrichment['missing_target']}"
            )
            if is_dry_run:
                self.stdout.write(self.style.SUCCESS(f"DRY RUN: {summary}"))
                if not enrichment["complete"]:
                    raise CommandError(
                        "Canonical dry run completed, but subsidy enrichment is "
                        f"incomplete: {enrichment.get('error') or 'link errors'}."
                    )
                return

            if sync_log:
                sync_log.records_processed = len(all_records)
                sync_log.records_created = stats['created']
                sync_log.records_updated = stats['updated']
                sync_log.records_skipped = stats['skipped']
                sync_log.details = {"subsidy_enrichment": enrichment}
                if enrichment["complete"]:
                    sync_log.mark_complete(success=True)
                else:
                    sync_log.mark_complete(
                        success=False,
                        error_message=(
                            "Canonical Youth fields were published, but subsidy "
                            "enrichment was incomplete and existing subsidy fields "
                            "were preserved."
                        ),
                    )

            age_bad = stats['age_unparseable_ids']
            self.stdout.write(self.style.SUCCESS(
                f"\nSync complete - {summary}, "
                f"school unmatched: {stats['school_unmatched']}, "
                f"mentor unmatched: {stats['mentor_unmatched']}, "
                f"age unparseable: {len(age_bad)}"
            ))
            if age_bad:
                self.stdout.write(self.style.WARNING(
                    f"Age was non-numeric (likely a blank/invalid DOB in Airtable) "
                    f"for employee IDs {age_bad}; stored as null. Fix the DOB at source."
                ))

            if not enrichment["complete"]:
                raise CommandError(
                    "Canonical Youth sync committed, but subsidy enrichment was "
                    "incomplete. Existing subsidy fields were preserved."
                )

        except Exception as e:
            if sync_log and sync_log.completed_at is None:
                try:
                    sync_log.mark_complete(success=False, error_message=str(e))
                except Exception:
                    pass
            self.stdout.write(self.style.ERROR(f"Sync failed: {e}"))
            raise

    def enrich_subsidies(self, basic_records, combined_records, error=None):
        """Join source-only subsidy fields without changing canonical identity."""
        combined_by_id = {
            record.get("id"): record
            for record in combined_records
            if record.get("id")
        }
        diagnostics = {
            "matched": 0,
            "missing_link": 0,
            "multiple_links": 0,
            "missing_target": 0,
            "complete": False,
        }
        if error:
            diagnostics["error"] = error
            return list(basic_records), diagnostics

        enriched = []
        for record in basic_records:
            result = deepcopy(record)
            fields = result.setdefault("fields", {})
            links = fields.get(COMBINED_LINK_FIELD) or []
            if not isinstance(links, list) or not links:
                diagnostics["missing_link"] += 1
                enriched.append(result)
                continue
            if len(links) != 1:
                diagnostics["multiple_links"] += 1
                enriched.append(result)
                continue
            combined = combined_by_id.get(links[0])
            if combined is None:
                diagnostics["missing_target"] += 1
                enriched.append(result)
                continue
            combined_fields = combined.get("fields", {})
            for source_field, destination_field in SUBSIDY_FIELD_MAP.items():
                if source_field in combined_fields:
                    fields[destination_field] = combined_fields[source_field]
                else:
                    fields.pop(destination_field, None)
            diagnostics["matched"] += 1
            enriched.append(result)

        diagnostics["complete"] = (
            diagnostics["matched"] == len(basic_records)
            and diagnostics["missing_link"] == 0
            and diagnostics["multiple_links"] == 0
            and diagnostics["missing_target"] == 0
        )
        return enriched, diagnostics

    def bulk_upsert(
        self,
        all_records,
        school_map,
        mentor_map,
        publish_subsidies=True,
        dry_run=False,
    ):
        # Resolve orphans before the write, but delete them only inside the
        # same transaction as creates and updates.
        incoming_airtable_ids = {r.get('id') for r in all_records if r.get('id')}
        orphans = Youth.objects.exclude(airtable_id__isnull=True).exclude(airtable_id__in=incoming_airtable_ids)
        orphan_count = orphans.count()

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
        age_unparseable_ids = []
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
            if not publish_subsidies:
                for field in (
                    "subsidy_funder",
                    "subsidy_status",
                    "subsidy_start_date",
                    "subsidy_end_date",
                ):
                    row_data.pop(field, None)

            # Deduplicate by employee_id and keep the first Airtable record seen.
            emp_id = row_data.get('employee_id')
            if emp_id in seen_employee_ids:
                skipped += 1
                continue
            seen_employee_ids.add(emp_id)

            if row_data.pop('_school_unmatched', False):
                school_unmatched += 1
            if row_data.pop('_mentor_unmatched', False):
                mentor_unmatched += 1
            if row_data.pop('_age_unparseable', False):
                age_unparseable_ids.append(emp_id)

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
        if publish_subsidies:
            update_fields.extend([
                'subsidy_funder', 'subsidy_status',
                'subsidy_start_date', 'subsidy_end_date',
            ])

        if not dry_run:
            with transaction.atomic():
                if orphan_count:
                    self.stdout.write(self.style.WARNING(
                        f"Deleting {orphan_count} orphan records not found in Airtable"
                    ))
                    orphans.delete()
                if new_objs:
                    Youth.objects.bulk_create(new_objs, batch_size=500)
                if update_objs:
                    Youth.objects.bulk_update(
                        update_objs,
                        update_fields,
                        batch_size=500,
                    )

        return {
            'created': len(new_objs),
            'updated': len(update_objs),
            'skipped': skipped,
            'deleted': orphan_count,
            'school_unmatched': school_unmatched,
            'mentor_unmatched': mentor_unmatched,
            'age_unparseable_ids': age_unparseable_ids,
        }

    def extract_row(self, record, school_map, mentor_map):
        fields = record.get('fields', {})

        def safe_first(name):
            val = fields.get(name)
            if isinstance(val, list):
                return val[0] if val else None
            return val or None

        employee_id = _coerce_int(fields.get('Employee ID'))
        if not employee_id:
            return None

        # Age is an Airtable formula field; a blank/invalid DOB makes it return
        # {'specialValue': 'NaN'}. Coerce to None and flag it so the source DOB
        # can be fixed, rather than crashing the IntegerField write.
        raw_age = fields.get('Age')
        age = _coerce_int(raw_age)
        age_unparseable = raw_age is not None and age is None

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
            age=age,
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
            subsidy_funder=safe_first('Funder'),
            subsidy_status=safe_first('SEF (Current Status) (from Office Link)'),
            subsidy_start_date=parse_date(
                safe_first('SEF Start Date (from Office Link)') or ''
            ),
            subsidy_end_date=parse_date(
                safe_first('SEF End Date (from Office Link)') or ''
            ),
            school_id=school_id,
            mentor_id=mentor_id,
            _school_unmatched=school_unmatched,
            _mentor_unmatched=mentor_unmatched,
            _age_unparseable=age_unparseable,
        )

    def fetch_from_airtable(self, base_id, table_id, token, fields=None):
        url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
        headers = {"Authorization": f"Bearer {token}"}
        all_records = []
        offset = None

        while True:
            params = [("pageSize", 100)]
            if fields:
                params.extend(("fields[]", field) for field in fields)
            if offset:
                params.append(("offset", offset))
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=30,
            )
            if response.status_code != 200:
                raise ValueError(f"Airtable API error {response.status_code}: {response.text[:200]}")
            data = response.json()
            all_records.extend(data.get('records', []))
            offset = data.get('offset')
            if not offset:
                break

        return all_records
