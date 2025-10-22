import os
import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.db import transaction
from dotenv import load_dotenv
from api.models import NumeracySessionChild


class Command(BaseCommand):
    help = "Sync numeracy session data from Airtable (flattened to child-level with readable names)"

    def handle(self, *args, **options):
        # --- Load environment variables ---
        load_dotenv()
        base_id = os.getenv("AIRTABLE_NUMERACY_SESSIONS_BASE_ID")
        table_name = os.getenv("AIRTABLE_NUMERACY_DAILY_SESSIONS_TABLE_NAME")
        token = os.getenv("AIRTABLE_TOKEN")

        if not all([base_id, table_name, token]):
            self.stdout.write(self.style.ERROR("❌ Missing Airtable credentials in environment variables"))
            return

        url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
        headers = {"Authorization": f"Bearer {token}"}
        all_records = []

        # --- Fetch all pages of Airtable records ---
        self.stdout.write(self.style.WARNING(f"Fetching records from: {url}"))
        while url:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(f"Error fetching data: {response.text}"))
                return

            data = response.json()
            all_records.extend(data.get("records", []))
            offset = data.get("offset")
            url = f"https://api.airtable.com/v0/{base_id}/{table_name}?offset={offset}" if offset else None

        self.stdout.write(self.style.SUCCESS(f"✅ Fetched {len(all_records)} session records."))

        # --- Helpers ---
        def safe_get(fields, name, default=""):
            val = fields.get(name, default)
            if isinstance(val, list):
                return val[0] if val else default
            return val

        def safe_array(fields, name):
            val = fields.get(name, [])
            return val if isinstance(val, list) else []

        # --- Parse and flatten data ---
        new_rows = []
        for record in all_records:
            fields = record.get("fields", {})

            # ✅ Use LOOKUP versions of linked fields
            nc_full_name = safe_get(fields, "Name (from NC Full Name)")
            numeracy_site = safe_get(fields, "Site Name (from Numeracy Sites)")
            child_names = safe_array(fields, "Learner Full Name (from Children in Session)")

            if not child_names:
                # Still create row (optional)
                new_rows.append(dict(
                    session_id=fields.get("Session ID"),
                    nc_full_name=nc_full_name,
                    numeracy_site=numeracy_site,
                    child_name=None,
                    sessions_capture_date=parse_date(fields.get("Sessions Capture Date", "")),
                    children_in_group=fields.get("Children In Group", 0),
                    created=fields.get("Created"),
                    current_count_level=safe_get(fields, "Current Count Level"),
                    baseline_count_level=safe_array(fields, "Basline Count Level"),
                    number_recognition=safe_get(fields, "Number Recognition"),
                    month=safe_get(fields, "Month").replace('"', ''),
                    week=safe_get(fields, "Week").replace('"', ''),
                    month_and_year=safe_get(fields, "Month and Year").replace('"', ''),
                    site_placement=safe_get(fields, "Site Placement"),
                    employee_id=str(safe_get(fields, "Employee ID")),
                    mentor=safe_get(fields, "Mentor"),
                    employment_status=safe_get(fields, "Employment Status"),
                    duplicate_flag=safe_get(fields, "Duplicate Flag"),
                ))
            else:
                for child in child_names:
                    new_rows.append(dict(
                        session_id=fields.get("Session ID"),
                        nc_full_name=nc_full_name,
                        numeracy_site=numeracy_site,
                        child_name=child,
                        sessions_capture_date=parse_date(fields.get("Sessions Capture Date", "")),
                        children_in_group=fields.get("Children In Group", 0),
                        created=fields.get("Created"),
                        current_count_level=safe_get(fields, "Current Count Level"),
                        baseline_count_level=safe_array(fields, "Basline Count Level"),
                        number_recognition=safe_get(fields, "Number Recognition"),
                        month=safe_get(fields, "Month").replace('"', ''),
                        week=safe_get(fields, "Week").replace('"', ''),
                        month_and_year=safe_get(fields, "Month and Year").replace('"', ''),
                        site_placement=safe_get(fields, "Site Placement"),
                        employee_id=str(safe_get(fields, "Employee ID")),
                        mentor=safe_get(fields, "Mentor"),
                        employment_status=safe_get(fields, "Employment Status"),
                        duplicate_flag=safe_get(fields, "Duplicate Flag"),
                    ))

        self.stdout.write(self.style.SUCCESS(f"📊 Flattened into {len(new_rows)} child-level rows."))

        # --- Bulk upsert into database ---
        with transaction.atomic():
            NumeracySessionChild.objects.all().delete()  # full refresh
            objs = [NumeracySessionChild(**row) for row in new_rows]
            NumeracySessionChild.objects.bulk_create(objs, batch_size=1000)

        self.stdout.write(self.style.SUCCESS("🎉 Airtable → Postgres sync complete!"))
