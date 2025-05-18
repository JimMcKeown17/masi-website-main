import os
import json
import time
import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from django.utils import timezone

# Import your models
from api.models import Youth, Child, Mentor, School, Session, AirtableSyncLog

class Command(BaseCommand):
    help = 'Import session data from Airtable and populate the Django models incrementally'

    def add_arguments(self, parser):
        parser.add_argument(
            '--full',
            action='store_true',
            help='Force a full import instead of incremental',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit the number of records to import (for testing)',
        )
        parser.add_argument(
            '--local',
            action='store_true',
            help='Use local JSON file instead of querying Airtable API',
        )

    def handle(self, *args, **options):
        # Start a new sync log
        sync_log = AirtableSyncLog.objects.create(sync_type='sessions')
        self.stdout.write(self.style.SUCCESS(f'Starting Airtable sessions sync (ID: {sync_log.id})...'))
        
        try:
            # Decide whether to do full or incremental import
            do_full_import = options['full']
            
            # Get data source (local file or API)
            if options['local']:
                records = self.get_data_from_file()
            else:
                records = self.fetch_from_airtable()
            
            if not records:
                sync_log.mark_complete(success=False, error_message="No records found to import")
                self.stdout.write(self.style.ERROR('No records found to import.'))
                return
                
            # Apply limit if specified (for testing)
            if options['limit'] and options['limit'] > 0:
                records = records[:options['limit']]
                self.stdout.write(f"Limited import to {options['limit']} records for testing")
                
            # Get the last sync time for incremental updates
            last_successful_sync = None
            if not do_full_import:
                last_syncs = AirtableSyncLog.objects.filter(
                    sync_type='sessions', 
                    success=True
                ).order_by('-completed_at')
                
                if last_syncs.exists():
                    last_successful_sync = last_syncs.first().started_at
                    self.stdout.write(f"Last successful sync: {last_successful_sync}")
            
            # Import the records
            self.import_sessions(records, sync_log, last_successful_sync)
            
            # Mark the sync as complete
            sync_log.mark_complete(success=True)
            self.stdout.write(self.style.SUCCESS(f'Sessions sync completed successfully!'))
            self.stdout.write(f'Created: {sync_log.records_created}, Updated: {sync_log.records_updated}, Skipped: {sync_log.records_skipped}')
                
        except Exception as e:
            # Log the error and mark sync as failed
            sync_log.mark_complete(success=False, error_message=str(e))
            self.stdout.write(self.style.ERROR(f'Error during sessions sync: {str(e)}'))
            raise
    
    def get_data_from_file(self):
        """Get session data from the local JSON file"""
        data_file = os.path.join(settings.BASE_DIR, 'data_exports', 'airtable_sessions_data.json')
        
        if not os.path.exists(data_file):
            self.stdout.write(self.style.ERROR(f"Data file not found: {data_file}"))
            return None
            
        self.stdout.write(f"Reading data from file: {data_file}")
        
        with open(data_file, 'r') as f:
            records = json.load(f)
            
        self.stdout.write(f"Loaded {len(records)} records from file")
        return records
        
    def fetch_from_airtable(self):
        """Fetch session data directly from Airtable API"""
        self.stdout.write("Fetching data from Airtable API...")
        
        # Get Airtable API key and base/table IDs from environment variables
        api_key = os.environ.get('AIRTABLE_API_KEY')
        base_id = os.environ.get('AIRTABLE_SESSIONS_BASE_ID')
        table_id = os.environ.get('AIRTABLE_SESSIONS_TABLE_ID')
        
        # Check if environment variables are set
        if not api_key:
            raise ValueError('Airtable API key not found in environment variables. Make sure AIRTABLE_API_KEY is set.')
        if not base_id:
            raise ValueError('Airtable base ID not found in environment variables. Make sure AIRTABLE_SESSIONS_BASE_ID is set.')
        if not table_id:
            raise ValueError('Airtable table ID not found in environment variables. Make sure AIRTABLE_SESSIONS_TABLE_ID is set.')
        
        # Construct the API URL
        url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
        
        # Set up headers with API key
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Initialize empty list for all records
        all_records = []
        
        # Airtable returns records in pages, so handle pagination
        params = {"pageSize": 100}  # Maximum page size
        
        # Keep track of progress
        record_count = 0
        page_count = 0
        
        while True:
            # Make the API request
            self.stdout.write(f"Fetching page {page_count + 1}...")
            response = requests.get(url, headers=headers, params=params)
            
            # Check if the request was successful
            if response.status_code != 200:
                raise ValueError(f"Error fetching data from Airtable: {response.status_code} - {response.text}")
            
            # Parse response as JSON
            data = response.json()
            
            # Get records from this page
            page_records = data.get('records', [])
            record_count += len(page_records)
            
            # Add records to our list
            all_records.extend(page_records)
            
            # Update progress
            page_count += 1
            self.stdout.write(f"Fetched {len(page_records)} records from page {page_count}")
            
            # Check if there are more records
            offset = data.get('offset')
            if not offset:
                break
            
            # Update params with offset for next page
            params['offset'] = offset
            
            # Add a slight delay to avoid hitting rate limits
            time.sleep(0.2)
        
        self.stdout.write(f"Fetched a total of {record_count} records from {page_count} pages")
        return all_records
    
    @transaction.atomic
    def import_sessions(self, records, sync_log, last_sync_time=None):
        """
        Import session records into Django models
        Uses atomic transaction to ensure data integrity
        """
        self.stdout.write(f"Starting import of {len(records)} session records...")
        
        # Initialize counters
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        # Process each record
        for i, record in enumerate(records):
            # Log progress every 100 records
            if i % 100 == 0:
                self.stdout.write(f"Processing record {i+1} of {len(records)}...")
                sync_log.records_processed = i + 1
                sync_log.save()
            
            record_id = record['id']
            fields = record['fields']
            
            # Check if this is a new record for incremental import
            if last_sync_time:
                created_time = datetime.strptime(record['createdTime'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
                if created_time < last_sync_time:
                    # Only update existing records if they already exist
                    if not Session.objects.filter(airtable_id=record_id).exists():
                        skipped_count += 1
                        continue
            
            # Get session ID - required field
            session_id = fields.get('Sessions ID')
            if not session_id:
                self.stdout.write(self.style.WARNING(f"Missing session ID for record {record_id}. Skipping."))
                skipped_count += 1
                continue
            
            # Process School
            school_airtable_id = fields.get('Schools', [None])[0]
            school_name = fields.get('Schools (from Schools)', [None])[0] or fields.get('School', [None])[0]
            site_type = fields.get('Site Type', [None])[0]
            
            if school_airtable_id and school_name:
                # Try to find by airtable_id first, then by name
                school = School.objects.filter(airtable_id=school_airtable_id).first()
                
                if not school:
                    school = School.objects.filter(name=school_name).first()
                
                if not school:
                    # Create a new school if it doesn't exist
                    school = School.objects.create(
                        airtable_id=school_airtable_id,
                        name=school_name,
                        site_type=site_type
                    )
            else:
                self.stdout.write(self.style.WARNING(f"Missing school data for session {record_id}. Skipping."))
                skipped_count += 1
                continue
            
            # Process Youth/Literacy Coach
            youth_airtable_id = fields.get('LC Full Name', [None])[0]
            youth_name = fields.get('Full Name (from LC Full Name)', [None])[0]
            employee_id = fields.get('Employee ID', [None])[0]
            
            if youth_airtable_id and youth_name:
                # Try to find by airtable_id first, then by employee_id, then by name
                youth = Youth.objects.filter(airtable_id=youth_airtable_id).first()
                
                if not youth and employee_id:
                    youth = Youth.objects.filter(employee_id=employee_id).first()
                
                if not youth:
                    youth = Youth.objects.filter(full_name=youth_name).first()
                
                if not youth:
                    # Create a placeholder youth if it doesn't exist
                    self.stdout.write(self.style.WARNING(f"Youth not found: {youth_name} (ID: {employee_id}). Creating placeholder."))
                    first_name, *last_names = youth_name.split()
                    last_name = ' '.join(last_names) if last_names else ''
                    
                    youth = Youth.objects.create(
                        airtable_id=youth_airtable_id,
                        employee_id=employee_id or 0,  # Use 0 if no employee_id is provided
                        first_names=first_name,
                        last_name=last_name,
                        full_name=youth_name,
                        school=school
                    )
            else:
                self.stdout.write(self.style.WARNING(f"Missing youth data for session {record_id}. Skipping."))
                skipped_count += 1
                continue
            
            # Process Child
            child_airtable_id = fields.get('Child Full Name', [None])[0]
            child_name = fields.get('Child Full Name (from Child Full Name)', [None])[0]
            mcode = fields.get('Mcode', [None])[0]
            grade = fields.get('Grade', [None])[0]
            on_programme = 'Yes' in fields.get('On the Programme', ['No'])
            
            if child_airtable_id and child_name:
                # Try to find by airtable_id first, then by name and school
                child = Child.objects.filter(airtable_id=child_airtable_id).first()
                
                if not child and mcode:
                    child = Child.objects.filter(mcode=mcode).first()
                
                if not child:
                    child = Child.objects.filter(full_name=child_name, school=school).first()
                
                if not child:
                    # Create a new child if it doesn't exist
                    child = Child.objects.create(
                        airtable_id=child_airtable_id,
                        full_name=child_name,
                        mcode=mcode,
                        grade=grade,
                        on_programme=on_programme,
                        school=school
                    )
            else:
                self.stdout.write(self.style.WARNING(f"Missing child data for session {record_id}. Skipping."))
                skipped_count += 1
                continue
            
            # Process Mentor
            mentor_name = fields.get('Mentor', [None])[0]
            mentor = None
            if mentor_name:
                # Try to find by name
                mentor = Mentor.objects.filter(name=mentor_name).first()
                
                if not mentor:
                    # Create a new mentor if it doesn't exist
                    mentor = Mentor.objects.create(name=mentor_name)
            
            # Process Session data
            total_weekly_sessions = fields.get('Total Weekly Sessions Received', 0)
            submitted_for_week = fields.get('Submitted for This Week', 0)
            week = fields.get('Week', '')
            month = fields.get('Month', '')
            month_year = fields.get('Month and Year', '')
            sessions_met_minimum = fields.get('Sessions Met Minimum', '')
            
            # Parse date fields
            try:
                capture_date = datetime.strptime(fields.get('Sessions Capture Date', ''), '%Y-%m-%d').date()
            except (ValueError, TypeError):
                capture_date = timezone.now().date()
                
            try:
                created_in_airtable = datetime.strptime(fields.get('Created', ''), '%Y-%m-%dT%H:%M:%S.%fZ')
            except (ValueError, TypeError):
                created_in_airtable = timezone.now()
            
            # Create or update Session
            session, created = Session.objects.update_or_create(
                airtable_id=record_id,
                defaults={
                    'session_id': session_id,
                    'youth': youth,
                    'child': child,
                    'school': school,
                    'mentor': mentor,
                    'total_weekly_sessions': total_weekly_sessions,
                    'submitted_for_week': submitted_for_week,
                    'week': week,
                    'month': month,
                    'month_year': month_year,
                    'sessions_met_minimum': sessions_met_minimum,
                    'capture_date': capture_date,
                    'created_in_airtable': created_in_airtable,
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
        
        # Update sync log with counts
        sync_log.records_created = created_count
        sync_log.records_updated = updated_count
        sync_log.records_skipped = skipped_count
        sync_log.records_processed = len(records)
        sync_log.save()
        
        self.stdout.write(self.style.SUCCESS(f"Import completed:"))
        self.stdout.write(f"- Created: {created_count}")
        self.stdout.write(f"- Updated: {updated_count}")
        self.stdout.write(f"- Skipped: {skipped_count}")