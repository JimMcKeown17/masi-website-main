# dashboards/management/commands/import_visits.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from api.models import School, MentorVisit
from django.db import transaction
import csv
import datetime
import os


class Command(BaseCommand):
    help = 'Import mentor visits from a consolidated CSV file with first/last names'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the consolidated CSV file')
        parser.add_argument('--dry-run', action='store_true', help='Preview imports without saving to database')

    def parse_date(self, date_str):
        """Try to parse date with various formats."""
        date_str = date_str.strip()
        
        formats = [
            '%Y-%m-%d',    # e.g., 2025-02-11
            '%m/%d/%y',    # e.g., 2/11/25
            '%m/%d/%Y',    # e.g., 2/11/2025
            '%-m/%-d/%y',  # e.g., 2/11/25 (no leading zeros)
        ]
        
        for fmt in formats:
            try:
                return datetime.datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        # If we get here, none of the formats worked
        raise ValueError(f"Could not parse date: {date_str}")

    def handle(self, *args, **options):
        csv_path = options['csv_file']
        dry_run = options['dry_run']
        
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f"Error: File {csv_path} does not exist."))
            return
        
        # Counters for reporting
        users_matched = 0
        users_not_found = 0
        schools_created = 0
        visits_created = 0
        duplicates_found = 0
        date_errors = 0
        
        # Keep track of unmapped names for reporting
        unmapped_names = set()
        
        try:
            # Read the CSV file
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # Verify the CSV has the required columns
                required_fields = ['first_name', 'last_name', 'school', 'visit_date']
                missing_fields = [field for field in required_fields if field not in reader.fieldnames]
                if missing_fields:
                    self.stdout.write(self.style.ERROR(
                        f"CSV is missing required fields: {', '.join(missing_fields)}"
                    ))
                    return
                
                # Start a transaction
                with transaction.atomic():
                    # Process each visit
                    for row_num, row in enumerate(reader, 2):  # Start from 2 for human-readable row numbers
                        first_name = row['first_name'].strip()
                        last_name = row['last_name'].strip()
                        full_name = f"{first_name} {last_name}"
                        
                        # Try to find the user by first and last name
                        try:
                            mentor = User.objects.get(
                                first_name__iexact=first_name,
                                last_name__iexact=last_name
                            )
                            self.stdout.write(f"Found user: {full_name}")
                            users_matched += 1
                        except User.MultipleObjectsReturned:
                            # If multiple users match, use the first one and warn
                            mentor = User.objects.filter(
                                first_name__iexact=first_name,
                                last_name__iexact=last_name
                            ).first()
                            self.stdout.write(self.style.WARNING(
                                f"Multiple users match name {full_name}, using first match"
                            ))
                            users_matched += 1
                        except User.DoesNotExist:
                            self.stdout.write(self.style.ERROR(f"Could not find user for: {full_name}"))
                            unmapped_names.add(full_name)
                            users_not_found += 1
                            continue
                        
                        # Get or create school
                        school_name = row['school']
                        try:
                            school = School.objects.get(name=school_name)
                        except School.DoesNotExist:
                            if dry_run:
                                self.stdout.write(self.style.WARNING(f"Would create new school: {school_name}"))
                                school = None
                            else:
                                school = School.objects.create(
                                    name=school_name,
                                    is_active=True
                                )
                                self.stdout.write(f"Created new school: {school_name}")
                                schools_created += 1
                        
                        # Parse the date
                        try:
                            visit_date = self.parse_date(row['visit_date'])
                        except ValueError as e:
                            self.stdout.write(self.style.ERROR(f"Row {row_num}: {str(e)}"))
                            date_errors += 1
                            continue
                        
                        # Get the indicator (if present)
                        indicator = row.get('indicator', '')
                        
                        # Check for existing visit
                        if not dry_run and mentor and school:
                            existing_visit = MentorVisit.objects.filter(
                                mentor=mentor,
                                school=school,
                                visit_date=visit_date
                            ).exists()
                            
                            if existing_visit:
                                self.stdout.write(f"Skipping duplicate: {full_name} visited {school_name} on {visit_date}")
                                duplicates_found += 1
                            else:
                                # Create visit
                                source_info = f"Source: {row.get('source_file', 'unknown')}"
                                if 'source_row' in row:
                                    source_info += f", row {row['source_row']}"
                                
                                visit = MentorVisit.objects.create(
                                    mentor=mentor,
                                    school=school,
                                    visit_date=visit_date,
                                    quality_rating=5,
                                    commentary=f"{source_info}. Indicator: {indicator}"
                                )
                                self.stdout.write(f"Created visit: {full_name} visited {school_name} on {visit_date}")
                                visits_created += 1
                        elif dry_run:
                            self.stdout.write(f"Would create visit: {full_name} visited {school_name} on {visit_date}")
                            visits_created += 1
                    
                    # If this is a dry run, roll back the transaction
                    if dry_run:
                        self.stdout.write(self.style.WARNING("DRY RUN - No changes committed to database"))
                        transaction.set_rollback(True)
            
            # Report results
            self.stdout.write(self.style.SUCCESS("\nSummary:"))
            self.stdout.write(f"Matched {users_matched} mentor names to users")
            self.stdout.write(f"Failed to match {users_not_found} mentor names")
            if date_errors > 0:
                self.stdout.write(f"Found {date_errors} date parsing errors")
            
            if unmapped_names:
                self.stdout.write("\nUnmapped mentor names:")
                self.stdout.write("----------------------")
                for name in sorted(unmapped_names):
                    self.stdout.write(f"- {name}")
            
            if dry_run:
                self.stdout.write(f"Would create {schools_created} new schools")
                self.stdout.write(f"Would create {visits_created} new mentor visits")
            else:
                self.stdout.write(f"Created {schools_created} new schools")
                self.stdout.write(f"Created {visits_created} new mentor visits")
                self.stdout.write(f"Found {duplicates_found} duplicate visits (skipped)")
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error importing data: {str(e)}"))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))