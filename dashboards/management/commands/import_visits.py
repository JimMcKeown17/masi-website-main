# dashboards/management/commands/import_visits.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from dashboards.models import School, MentorVisit
from django.db import transaction
import csv
import datetime
import os


class Command(BaseCommand):
    help = 'Import mentor visits from a consolidated CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the consolidated CSV file')
        parser.add_argument('--dry-run', action='store_true', help='Preview imports without saving to database')

    def handle(self, *args, **options):
        csv_path = options['csv_file']
        dry_run = options['dry_run']
        
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f"Error: File {csv_path} does not exist."))
            return
        
        # Counters for reporting
        users_created = 0
        schools_created = 0
        visits_created = 0
        duplicates_found = 0
        
        # Optional mentor username mapping if needed
        # MENTOR_NAME_MAPPING = {
        #     "ziyanda": "ziyanda_actual_username",
        # }
        
        try:
            # Read the CSV file
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # Start a transaction or enter a dry-run context
                with transaction.atomic():
                    # Process each visit
                    for row in reader:
                        # Get mentor name
                        mentor_name = row['mentor']
                        # mentor_name = MENTOR_NAME_MAPPING.get(mentor_name, mentor_name)  # Uncomment if mapping needed
                        
                        # Get or create mentor user
                        try:
                            mentor = User.objects.get(username=mentor_name)
                            self.stdout.write(f"Using existing user: {mentor_name}")
                        except User.DoesNotExist:
                            if dry_run:
                                self.stdout.write(self.style.WARNING(f"Would create new user: {mentor_name}"))
                                mentor = None
                            else:
                                mentor = User.objects.create_user(
                                    username=mentor_name,
                                    first_name=mentor_name.title(),
                                    email=f"{mentor_name.lower()}@example.com",
                                    password="changeme123"  # Temporary password
                                )
                                self.stdout.write(self.style.SUCCESS(f"Created new user: {mentor_name}"))
                                users_created += 1
                        
                        # Get or create school
                        school_name = row['school']
                        try:
                            school = School.objects.get(name=school_name)
                            self.stdout.write(f"Using existing school: {school_name}")
                        except School.DoesNotExist:
                            if dry_run:
                                self.stdout.write(self.style.WARNING(f"Would create new school: {school_name}"))
                                school = None
                            else:
                                school = School.objects.create(
                                    name=school_name,
                                    is_active=True
                                )
                                self.stdout.write(self.style.SUCCESS(f"Created new school: {school_name}"))
                                schools_created += 1
                        
                        # Parse the date
                        visit_date = datetime.datetime.strptime(row['visit_date'], '%Y-%m-%d').date()
                        
                        # Check for existing visit
                        if not dry_run and mentor and school:
                            existing_visit = MentorVisit.objects.filter(
                                mentor=mentor,
                                school=school,
                                visit_date=visit_date
                            ).exists()
                            
                            if existing_visit:
                                self.stdout.write(f"Skipping duplicate: {mentor_name} visited {school_name} on {visit_date}")
                                duplicates_found += 1
                            else:
                                # Create visit
                                visit = MentorVisit.objects.create(
                                    mentor=mentor,
                                    school=school,
                                    visit_date=visit_date,
                                    quality_rating=5,
                                    commentary=f"Imported from {row['source_file']} row {row['source_row']}. Indicator: {row['indicator']}"
                                )
                                self.stdout.write(f"Created visit: {mentor_name} visited {school_name} on {visit_date}")
                                visits_created += 1
                        elif dry_run:
                            self.stdout.write(self.style.WARNING(
                                f"Would create visit: {mentor_name} visited {school_name} on {visit_date}"
                            ))
                            visits_created += 1
                    
                    # If this is a dry run, roll back the transaction
                    if dry_run:
                        self.stdout.write(self.style.WARNING("DRY RUN - No changes committed to database"))
                        transaction.set_rollback(True)
            
            # Report results
            self.stdout.write(self.style.SUCCESS("\nSummary:"))
            if dry_run:
                self.stdout.write(f"Would create {users_created} new users (mentors)")
                self.stdout.write(f"Would create {schools_created} new schools")
                self.stdout.write(f"Would create {visits_created} new mentor visits")
            else:
                self.stdout.write(f"Created {users_created} new users (mentors)")
                self.stdout.write(f"Created {schools_created} new schools")
                self.stdout.write(f"Created {visits_created} new mentor visits")
                self.stdout.write(f"Found {duplicates_found} duplicate visits (skipped)")
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error importing data: {str(e)}"))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))