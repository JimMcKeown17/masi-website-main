import os
import json
import time
import requests
from datetime import datetime
from pytz import UTC
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction, IntegrityError
from django.utils import timezone
import psycopg2

# Import your models
from api.models import Youth, Mentor, School, AirtableSyncLog

class Command(BaseCommand):
    help = 'Import youth data from Airtable and populate the Django models incrementally'

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
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing records with the same employee_id',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed logs for skipped records',
        )

    def handle(self, *args, **options):
        # Start a new sync log
        sync_log = AirtableSyncLog.objects.create(sync_type='youth')
        self.stdout.write(self.style.SUCCESS(f'Starting Airtable youth sync (ID: {sync_log.id})...'))
        
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
                    sync_type='youth', 
                    success=True
                ).order_by('-completed_at')
                
                if last_syncs.exists():
                    last_successful_sync = last_syncs.first().started_at
                    self.stdout.write(f"Last successful sync: {last_successful_sync}")
            
            # Import the records
            self.import_youth(records, sync_log, last_successful_sync, options)
            
            # Mark the sync as complete
            sync_log.mark_complete(success=True)
            self.stdout.write(self.style.SUCCESS(f'Youth sync completed successfully!'))
            self.stdout.write(f'Created: {sync_log.records_created}, Updated: {sync_log.records_updated}, Skipped: {sync_log.records_skipped}')
                
        except Exception as e:
            # Log the error and mark sync as failed
            sync_log.mark_complete(success=False, error_message=str(e))
            self.stdout.write(self.style.ERROR(f'Error during youth sync: {str(e)}'))
            raise
    
    def get_data_from_file(self):
        """Get youth data from the local JSON file"""
        data_file = os.path.join(settings.BASE_DIR, 'data_exports', 'airtable_youth_data.json')
        
        if not os.path.exists(data_file):
            self.stdout.write(self.style.ERROR(f"Data file not found: {data_file}"))
            return None
            
        self.stdout.write(f"Reading data from file: {data_file}")
        
        with open(data_file, 'r') as f:
            records = json.load(f)
            
        self.stdout.write(f"Loaded {len(records)} records from file")
        return records
        
    def fetch_from_airtable(self):
        """Fetch youth data directly from Airtable API"""
        self.stdout.write("Fetching data from Airtable API...")
        
        # Get Airtable API key and base/table IDs from environment variables
        api_key = os.environ.get('AIRTABLE_API_KEY')
        base_id = os.environ.get('AIRTABLE_YOUTH_BASE_ID')
        table_id = os.environ.get('AIRTABLE_COMBINED_YOUTH_DATA_TABLE_ID')
        
        # Check if environment variables are set
        if not api_key:
            raise ValueError('Airtable API key not found in environment variables. Make sure AIRTABLE_API_KEY is set.')
        if not base_id:
            raise ValueError('Airtable base ID not found in environment variables. Make sure AIRTABLE_YOUTH_BASE_ID is set.')
        if not table_id:
            raise ValueError('Airtable table ID not found in environment variables. Make sure AIRTABLE_COMBINED_YOUTH_DATA_TABLE_ID is set.')
        
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
    
    # Helper function to extract single value from potential list
    def extract_value(self, value):
        """Extract a single value from a potential list or return the value itself"""
        if isinstance(value, list) and len(value) > 0:
            return value[0]
        return value
    
    @transaction.atomic
    def import_youth(self, records, sync_log, last_sync_time=None, options=None):
        """
        Import youth records into Django models
        Uses atomic transaction to ensure data integrity
        """
        self.stdout.write(f"Starting import of {len(records)} youth records...")
        
        # Initialize counters
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        # Initialize counters for skip reasons
        skip_reasons = {
            'no_employee_id': 0,
            'duplicate_in_batch': 0,
            'already_exists': 0,
            'integrity_error': 0,
            'other_error': 0
        }
        
        # For collecting skipped records details
        skipped_records = []
        
        # Track processed employee_ids to avoid duplicates within this import
        processed_employee_ids = set()
        
        # Process each record
        for i, record in enumerate(records):
            # Log progress every 100 records
            if i % 100 == 0:
                self.stdout.write(f"Processing record {i+1} of {len(records)}...")
                sync_log.records_processed = i + 1
                sync_log.save()
            
            record_id = record['id']
            fields = record['fields']
            
            # Get employee ID - required field
            employee_id = self.extract_value(fields.get('Employee ID'))
            
            if not employee_id:
                skip_reasons['no_employee_id'] += 1
                if options.get('verbose'):
                    skipped_records.append({
                        'record_id': record_id,
                        'reason': f"Missing employee ID",
                        'details': f"Fields: {fields}"
                    })
                self.stdout.write(self.style.WARNING(f"Missing employee ID for record {record_id}. Skipping."))
                skipped_count += 1
                continue
            
            # Check for duplicate employee_id within this import batch
            if employee_id in processed_employee_ids:
                skip_reasons['duplicate_in_batch'] += 1
                if options.get('verbose'):
                    skipped_records.append({
                        'record_id': record_id,
                        'employee_id': employee_id,
                        'reason': f"Duplicate employee_id within this import batch",
                        'details': f"This employee_id has already been processed in this batch"
                    })
                self.stdout.write(self.style.WARNING(
                    f"Found duplicate employee_id {employee_id} within this import batch. Skipping."))
                skipped_count += 1
                continue
            
            # Process mentor (if exists)
            mentor_name = self.extract_value(fields.get('Mentor'))
            mentor = None
            if mentor_name and len(mentor_name) > 20:
                self.stdout.write(self.style.ERROR(
                    f"Mentor name too long: '{mentor_name}' (length: {len(mentor_name)}) for record {record_id}, employee_id {employee_id}"
                ))
            if mentor_name:
                mentor, mentor_created = Mentor.objects.get_or_create(name=mentor_name)
            
            # Process school (if exists)
            school_name = self.extract_value(fields.get('Site Placement'))
            school_airtable_id = self.extract_value(fields.get('Schools')) if 'Schools' in fields else None
            site_type = self.extract_value(fields.get('Site Type'))
            
            school = None
            if school_name:
                # Try to find by airtable_id first, then by name
                if school_airtable_id:
                    school = School.objects.filter(airtable_id=school_airtable_id).first()
                
                if not school:
                    school = School.objects.filter(name=school_name).first()
                
                if not school:
                    # Create a new school if it doesn't exist
                    school = School.objects.create(
                        name=school_name,
                        airtable_id=school_airtable_id,
                        site_type=site_type
                    )
            
            # Process youth data - extract single values from potential lists
            first_names = self.extract_value(fields.get('First Names', ''))
            last_name = self.extract_value(fields.get('Last Name', ''))
            full_name = self.extract_value(fields.get('Full Name', ''))
            
            # Basic information
            job_title = self.extract_value(fields.get('Job Title'))
            employment_status = self.extract_value(fields.get('Employment Status', 'Active'))
            
            # Timestamps
            try:
                dob_str = self.extract_value(fields.get('DOB'))
                dob = datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None
            except (ValueError, TypeError):
                dob = None
                
            try:
                start_date_str = self.extract_value(fields.get('Start Date'))
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
            except (ValueError, TypeError):
                start_date = None
                
            try:
                end_date_str = self.extract_value(fields.get('End Date'))
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
            except (ValueError, TypeError):
                end_date = None
            
            # Demographics - process potential lists
            age_value = fields.get('Age')
            age = int(self.extract_value(age_value)) if age_value is not None else None
            
            gender = self.extract_value(fields.get('Gender'))
            race = self.extract_value(fields.get('Race'))
            
            # ID information
            id_type = self.extract_value(fields.get('ID Type'))
            rsa_id_number = self.extract_value(fields.get('RSA ID Number'))
            foreign_id_number = self.extract_value(fields.get('Foreign ID Number'))
            
            # Contact information
            cell_phone_number = self.extract_value(fields.get('Cell Phone Number'))
            email = self.extract_value(fields.get('Email'))
            emergency_number = self.extract_value(fields.get('Emergency Number'))
            
            # Address
            street_number = self.extract_value(fields.get('Street Number'))
            street_address = self.extract_value(fields.get('Street Address'))
            suburb_township = self.extract_value(fields.get('Suburb/Township'))
            city_or_town = self.extract_value(fields.get('City or Town'))
            postal_code = self.extract_value(fields.get('Postal Code'))
            
            # Employment details
            reason_for_leaving = self.extract_value(fields.get('Reason for Leaving'))
            income_tax_number = self.extract_value(fields.get('Income Tax Number'))
            
            # Banking details
            bank_name = self.extract_value(fields.get('Bank Name'))
            account_type = self.extract_value(fields.get('Account type'))
            branch_code = self.extract_value(fields.get('Branch code'))
            account_number = self.extract_value(fields.get('Account number'))
            
            # Prepare defaults dictionary for create/update
            defaults = {
                'first_names': first_names,
                'last_name': last_name,
                'full_name': full_name or f"{first_names} {last_name}".strip(),
                'job_title': job_title,
                'employment_status': employment_status,
                'dob': dob,
                'age': age,
                'gender': gender,
                'race': race,
                'id_type': id_type,
                'rsa_id_number': rsa_id_number,
                'foreign_id_number': foreign_id_number,
                'cell_phone_number': cell_phone_number,
                'email': email,
                'emergency_number': emergency_number,
                'street_number': street_number,
                'street_address': street_address,
                'suburb_township': suburb_township,
                'city_or_town': city_or_town,
                'postal_code': postal_code,
                'start_date': start_date,
                'end_date': end_date,
                'reason_for_leaving': reason_for_leaving,
                'income_tax_number': income_tax_number,
                'bank_name': bank_name,
                'account_type': account_type,
                'branch_code': branch_code,
                'account_number': account_number,
                'school': school,
                'mentor': mentor,
            }
            
            try:
                # First, check if a youth with this employee_id already exists
                existing_youth = Youth.objects.filter(employee_id=employee_id).first()
                
                if existing_youth and options.get('update_existing'):
                    for key, value in defaults.items():
                        setattr(existing_youth, key, value)
                    existing_youth.airtable_id = record_id
                    try:
                        existing_youth.save()
                    except psycopg2.DataError as e:
                        error_fields = {k: (str(v), len(str(v)) if v is not None else 0) for k, v in defaults.items()}
                        self.stdout.write(self.style.ERROR(
                            f"DataError for record {record_id} (employee_id: {employee_id}): {e}\nField values/lengths: {error_fields}"
                        ))
                        raise
                    updated_count += 1
                    if i < 5 or i % 100 == 0:
                        self.stdout.write(f"Updated existing youth with employee_id {employee_id}: {existing_youth.full_name}")
                
                # If no existing youth or not updating existing, try to create/update based on airtable_id
                elif not existing_youth:
                    try:
                        youth, created = Youth.objects.update_or_create(
                            airtable_id=record_id,
                            defaults={
                                'employee_id': employee_id,
                                **defaults
                            }
                        )
                    except psycopg2.DataError as e:
                        error_fields = {k: (str(v), len(str(v)) if v is not None else 0) for k, v in defaults.items()}
                        self.stdout.write(self.style.ERROR(
                            f"DataError for record {record_id} (employee_id: {employee_id}): {e}\nField values/lengths: {error_fields}"
                        ))
                        raise
                    if created:
                        created_count += 1
                        if i < 5 or i % 100 == 0:
                            self.stdout.write(self.style.SUCCESS(f"Created youth: {youth.full_name} (#{youth.employee_id})"))
                    else:
                        updated_count += 1
                        if i < 5 or i % 100 == 0:
                            self.stdout.write(f"Updated youth: {youth.full_name} (#{youth.employee_id})")
                else:
                    # Skip this record as it would create a duplicate
                    skip_reasons['already_exists'] += 1
                    if options.get('verbose'):
                        skipped_records.append({
                            'record_id': record_id,
                            'employee_id': employee_id,
                            'reason': f"Already exists and --update-existing not specified",
                            'details': f"Youth record with employee_id {employee_id} already exists"
                        })
                    self.stdout.write(self.style.WARNING(
                        f"Skipping record with employee_id {employee_id} - already exists and --update-existing not specified"))
                    skipped_count += 1
                
                # Add employee_id to processed set
                processed_employee_ids.add(employee_id)
                
            except IntegrityError as e:
                error_msg = str(e)
                skip_reasons['integrity_error'] += 1
                if options.get('verbose'):
                    skipped_records.append({
                        'record_id': record_id,
                        'employee_id': employee_id,
                        'reason': f"IntegrityError",
                        'details': error_msg
                    })
                if "duplicate key value violates unique constraint" in error_msg:
                    self.stdout.write(self.style.ERROR(
                        f"Duplicate key error for record {record_id} with employee_id {employee_id}: {error_msg}"))
                    skipped_count += 1
                else:
                    raise
            except Exception as e:
                error_msg = str(e)
                skip_reasons['other_error'] += 1
                if options.get('verbose'):
                    skipped_records.append({
                        'record_id': record_id,
                        'employee_id': employee_id if employee_id else "N/A",
                        'reason': f"Other error",
                        'details': error_msg
                    })
                self.stdout.write(self.style.ERROR(f"Error processing record {record_id}: {error_msg}"))
                skipped_count += 1
        
        # Update sync log with counts
        sync_log.records_created = created_count
        sync_log.records_updated = updated_count
        sync_log.records_skipped = skipped_count
        sync_log.records_processed = len(records)
        sync_log.save()
        
        # Print skip reason summary
        self.stdout.write("\nSkip Reason Summary:")
        for reason, count in skip_reasons.items():
            if count > 0:
                self.stdout.write(f"- {reason.replace('_', ' ').title()}: {count}")
        
        # Write detailed skip log if verbose mode is on
        if options.get('verbose') and skipped_records:
            self.stdout.write("\nDetailed skip log:")
            for sr in skipped_records[:20]:  # Show first 20 for brevity
                self.stdout.write(f"  Record ID: {sr['record_id']}")
                if 'employee_id' in sr:
                    self.stdout.write(f"  Employee ID: {sr['employee_id']}")
                self.stdout.write(f"  Reason: {sr['reason']}")
                self.stdout.write(f"  Details: {sr['details']}")
                self.stdout.write("")
            
            if len(skipped_records) > 20:
                self.stdout.write(f"  ... and {len(skipped_records) - 20} more skipped records")
            
            # Option to write to a file for further analysis
            log_file = os.path.join(settings.BASE_DIR, 'logs', f'youth_import_skip_log_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json')
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            with open(log_file, 'w') as f:
                json.dump({
                    'summary': skip_reasons,
                    'records': skipped_records
                }, f, indent=2)
            self.stdout.write(f"\nDetailed skip log written to: {log_file}")
        
        self.stdout.write(self.style.SUCCESS(f"Import completed:"))
        self.stdout.write(f"- Created: {created_count}")
        self.stdout.write(f"- Updated: {updated_count}")
        self.stdout.write(f"- Skipped: {skipped_count}")