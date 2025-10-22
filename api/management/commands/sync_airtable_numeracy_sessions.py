import os
import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.db import transaction
from dotenv import load_dotenv
from api.models import NumeracySessionChild

class Command(BaseCommand):
    help = "Sync numeracy session data from Airtable (flattened to child-level)"

    def handle(self, *args, **options):
        # Load environment variables
        load_dotenv()

        base_id = os.getenv("AIRTABLE_NUMERACY_SESSIONS_BASE_ID")
        table_name = os.getenv("AIRTABLE_NUMERACY_DAILY_SESSIONS_TABLE_NAME")
        token = os.getenv("AIRTABLE_TOKEN")

        if not all([base_id, table_name, token]):
            self.stdout.write(self.style.ERROR("Missing Airtable credentials in environment variables"))
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

        # --- Parse and flatten data ---
        new_rows = []
        for record in all_records:
            fields = record.get("fields", {})

            def safe_get(name, default=""):
                val = fields.get(name, default)
                if isinstance(val, list):
                    return val[0] if val else default
                return val

            def safe_array(name):
                val = fields.get(name, [])
                return val if isinstance(val, list) else []

            children = safe_array("Children in Session")

            # If no children, still keep one row (optional)
            if not children:
                new_rows.append(dict(
                    session_id=fields.get("Session ID"),
                    nc_full_name=safe_get("NC Full Name"),
                    numeracy_site=safe_get("Numeracy Sites"),
                    child_name=None,
                    sessions_capture_date=parse_date(fields.get("Sessions Capture Date", "")),
                    children_in_group=fields.get("Children In Group", 0),
                    created=fields.get("Created"),
                    current_count_level=safe_get("Current Count Level"),
                    baseline_count_level=safe_array("Basline Count Level"),
                    number_recognition=safe_get("Number Recognition"),
                    month=safe_get("Month").replace('"', ''),
                    week=safe_get("Week").replace('"', ''),
                    month_and_year=safe_get("Month and Year").replace('"', ''),
                    all_sites=safe_array("All Sites"),
                    site_placement=safe_get("Site Placement"),
                    employee_id=str(safe_get("Employee ID")),
                    mentor=safe_get("Mentor"),
                    employment_status=safe_get("Employment Status"),
                    duplicate_flag=safe_get("Duplicate Flag"),
                ))
            else:
                for child in children:
                    new_rows.append(dict(
                        session_id=fields.get("Session ID"),
                        nc_full_name=safe_get("NC Full Name"),
                        numeracy_site=safe_get("Numeracy Sites"),
                        child_name=child,
                        sessions_capture_date=parse_date(fields.get("Sessions Capture Date", "")),
                        children_in_group=fields.get("Children In Group", 0),
                        created=fields.get("Created"),
                        current_count_level=safe_get("Current Count Level"),
                        baseline_count_level=safe_array("Basline Count Level"),
                        number_recognition=safe_get("Number Recognition"),
                        month=safe_get("Month").replace('"', ''),
                        week=safe_get("Week").replace('"', ''),
                        month_and_year=safe_get("Month and Year").replace('"', ''),
                        all_sites=safe_array("All Sites"),
                        site_placement=safe_get("Site Placement"),
                        employee_id=str(safe_get("Employee ID")),
                        mentor=safe_get("Mentor"),
                        employment_status=safe_get("Employment Status"),
                        duplicate_flag=safe_get("Duplicate Flag"),
                    ))

        self.stdout.write(self.style.SUCCESS(f"Flattened into {len(new_rows)} child-level rows."))

        # --- Bulk upsert into database ---
        with transaction.atomic():
            NumeracySessionChild.objects.all().delete()  # optional: full refresh
            objs = [NumeracySessionChild(**row) for row in new_rows]
            NumeracySessionChild.objects.bulk_create(objs, batch_size=1000)

        self.stdout.write(self.style.SUCCESS("🎉 Airtable → Postgres sync complete!"))
