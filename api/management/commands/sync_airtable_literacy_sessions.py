from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.db import transaction
import requests
from api.models import LiteracySession
import os
from dotenv import load_dotenv


class Command(BaseCommand):
    help = "Sync literacy session data from Airtable into the local Postgres database"

    def handle(self, *args, **options):
        # --- Load .env file from project root
        load_dotenv()

        base_id = os.getenv("AIRTABLE_MASI_WEEKLY_SESSIONS_BASE_ID")
        table_name = os.getenv("AIRTABLE_MASI_WEEKLY_SESSIONS_TABLE_NAME")
        token = os.getenv("AIRTABLE_TOKEN")

        if not all([base_id, table_name, token]):
            self.stdout.write(self.style.ERROR(
                f"Missing Airtable credentials in environment variables.\n"
                f"  AIRTABLE_MASI_WEEKLY_SESSIONS_BASE_ID={bool(base_id)}\n"
                f"  AIRTABLE_MASI_WEEKLY_SESSIONS_TABLE_NAME={bool(table_name)}\n"
                f"  AIRTABLE_TOKEN={bool(token)}"
            ))
            return

        url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
        headers = {"Authorization": f"Bearer {token}"}
        all_records = []

        self.stdout.write(self.style.NOTICE(f"Fetching records from: {url}"))

        # --- Fetch all records (handle pagination)
        while url:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(f"Error fetching data: {response.text[:200]}"))
                return

            data = response.json()
            all_records.extend(data.get("records", []))
            offset = data.get("offset")
            url = f"https://api.airtable.com/v0/{base_id}/{table_name}?offset={offset}" if offset else None

        self.stdout.write(self.style.SUCCESS(f"✅ Fetched {len(all_records)} records from Airtable."))

        # --- Parse and insert/update
        with transaction.atomic():
            for record in all_records:
                fields = record.get("fields", {})

                def safe_get(name, default=""):
                    val = fields.get(name, default)
                    if isinstance(val, list):
                        return val[0] if val else default
                    if isinstance(val, dict):
                        # If it's a dict, try to get a reasonable string representation
                        # Common Airtable patterns: {'name': 'value'} or {'id': 'xxx', 'name': 'value'}
                        return val.get('name', val.get('id', str(val)))
                    return val

                def safe_array(name):
                    val = fields.get(name, [])
                    return val if isinstance(val, list) else []

                LiteracySession.objects.update_or_create(
                    session_id=fields.get("Sessions ID"),
                    defaults=dict(
                        lc_full_name=safe_get("Full Name (from LC Full Name)"),
                        child_full_name=safe_get("Child Full Name (from Child Full Name)"),
                        school=safe_get("Schools (from Schools)"),
                        grade=safe_get("Grade"),
                        sessions_capture_date=parse_date(fields.get("Sessions Capture Date", "")),
                        total_weekly_sessions_received=fields.get("Total Weekly Sessions Received", 0),
                        reading_level=fields.get("Reading Level", ""),
                        letters_done=safe_array("Letters Done"),
                        mentor=safe_get("Mentor"),
                        site_type=safe_get("Site Type"),
                        on_the_programme=safe_get("On the Programme"),
                        month=safe_get("Month", "").replace('"', ''),
                        week=safe_get("Week", "").replace('"', ''),
                        month_and_year=safe_get("Month and Year", "").replace('"', ''),
                        created=fields.get("Created"),
                        sessions_met_minimum=safe_get("Sessions Met Minimum"),
                        duplicate_flag=fields.get("Duplicate Flag", ""),
                        employee_id=str(safe_get("Employee ID", "")),
                        mcode=str(fields.get("Mcode", "")),
                    ),
                )

        self.stdout.write(self.style.SUCCESS("🎉 Airtable → Postgres sync complete!"))