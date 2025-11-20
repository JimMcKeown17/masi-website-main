import os
import json
import time
import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from api.models import School, AirtableSyncLog

class Command(BaseCommand):
    help = 'Sync schools from Airtable - safely update existing and add new schools'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without actually saving to database',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit the number of records to process (for testing)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed logs for all operations',
        )
        parser.add_argument(
            '--local',
            action='store_true',
            help='Use local JSON file instead of querying Airtable API',
        )
        parser.add_argument(
            '--link-existing',
            action='store_true',
            help='Link existing schools (by name match) to Airtable instead of creating duplicates',
        )

    def handle(self, *args, **options):
        is_dry_run = options['dry_run']
        
        # Start a new sync log (only if not dry-run)
        if not is_dry_run:
            sync_log = AirtableSyncLog.objects.create(sync_type='schools')
            self.stdout.write(self.style.SUCCESS(f'Starting Airtable schools sync (ID: {sync_log.id})...'))
        else:
            sync_log = None
            self.stdout.write(self.style.WARNING('=== DRY RUN MODE - No changes will be saved ===\n'))
        
        try:
            # Get data source (local file or API)
            if options['local']:
                records = self.get_data_from_file()
            else:
                records = self.fetch_from_airtable()
            
            if not records:
                if sync_log:
                    sync_log.mark_complete(success=False, error_message="No records found")
                self.stdout.write(self.style.ERROR('No records found to sync.'))
                return
                
            # Apply limit if specified (for testing)
            if options['limit'] and options['limit'] > 0:
                records = records[:options['limit']]
                self.stdout.write(f"Limited sync to {options['limit']} records for testing\n")
                
            # Sync the schools
            stats = self.sync_schools(records, is_dry_run, options)
            
            # Mark the sync as complete
            if sync_log:
                sync_log.records_created = stats['created']
                sync_log.records_updated = stats['updated'] + stats['linked']  # Count linked as updated
                sync_log.records_skipped = stats['skipped']
                sync_log.records_processed = stats['processed']
                sync_log.mark_complete(success=True)
            
            # Print summary
            if is_dry_run:
                self.stdout.write(self.style.WARNING('\n=== DRY RUN COMPLETE - No changes were saved ==='))
            else:
                self.stdout.write(self.style.SUCCESS('\n=== SYNC COMPLETED SUCCESSFULLY ==='))
            
            self.stdout.write(f'Processed: {stats["processed"]}')
            if stats["linked"] > 0:
                self.stdout.write(f'Linked existing: {stats["linked"]}')
            self.stdout.write(f'Created: {stats["created"]}')
            self.stdout.write(f'Updated: {stats["updated"]}')
            self.stdout.write(f'Skipped: {stats["skipped"]}')
            self.stdout.write(f'No changes needed: {stats["unchanged"]}')
                
        except Exception as e:
            # Log the error and mark sync as failed
            if sync_log:
                sync_log.mark_complete(success=False, error_message=str(e))
            self.stdout.write(self.style.ERROR(f'Error during schools sync: {str(e)}'))
            raise
    
    def get_data_from_file(self):
        """Get schools data from a local JSON file"""
        data_file = os.path.join(settings.BASE_DIR, 'data_exports', 'airtable_schools_data.json')
        
        if not os.path.exists(data_file):
            self.stdout.write(self.style.ERROR(f"Data file not found: {data_file}"))
            return None
            
        self.stdout.write(f"Reading data from file: {data_file}")
        
        with open(data_file, 'r') as f:
            data = json.load(f)
            
        # Handle both raw API response format and pre-processed format
        if isinstance(data, dict) and 'records' in data:
            records = data['records']
        elif isinstance(data, list):
            records = data
        else:
            self.stdout.write(self.style.ERROR("Invalid data format in file"))
            return None
            
        self.stdout.write(f"Loaded {len(records)} records from file\n")
        return records
        
    def fetch_from_airtable(self):
        """Fetch schools data directly from Airtable API"""
        self.stdout.write("Fetching data from Airtable API...")
        
        # Get Airtable API key and base/table IDs from environment variables
        api_key = os.environ.get('AIRTABLE_API_KEY')
        base_id = os.environ.get('AIRTABLE_SCHOOLS_BASE_ID')
        table_id = os.environ.get('AIRTABLE_SCHOOLS_TABLE_ID')
        
        # Check if environment variables are set
        if not api_key:
            raise ValueError('AIRTABLE_API_KEY not found in environment variables')
        if not base_id:
            raise ValueError('AIRTABLE_SCHOOLS_BASE_ID not found in environment variables')
        if not table_id:
            raise ValueError('AIRTABLE_SCHOOLS_TABLE_ID not found in environment variables')
        
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
        
        self.stdout.write(f"Fetched a total of {record_count} records from {page_count} pages\n")
        return all_records
    
    def extract_value(self, value):
        """Extract a single value from a potential list or return the value itself"""
        if isinstance(value, list) and len(value) > 0:
            return value[0]
        return value
    
    def map_airtable_school_type(self, airtable_types):
        """Map Airtable school type to Django model choices
        
        Airtable Type is multiple select, so we take the first/primary type
        Mapping: Primary -> Primary School, ECD -> ECDC, High School -> Secondary School
        """
        if not airtable_types:
            return None
        
        # Handle if it's a list (multiple select field)
        if isinstance(airtable_types, list):
            if len(airtable_types) == 0:
                return None
            # Take the first type as primary
            primary_type = airtable_types[0]
        else:
            primary_type = airtable_types
        
        # Mapping from Airtable to Django SCHOOL_TYPE_CHOICES
        type_mapping = {
            'ECD': 'ECDC',
            'Primary': 'Primary School',
            'High School': 'Secondary School',
        }
        
        return type_mapping.get(primary_type, 'Other')
    
    def format_phone_number(self, phone):
        """Clean and format phone number"""
        if not phone:
            return None
        
        # Remove parentheses, spaces, and dashes
        phone = str(phone).replace('(', '').replace(')', '').replace('-', '').replace(' ', '')
        return phone if phone else None
    
    def has_changes(self, school, new_data):
        """Check if any fields would be changed"""
        for field, new_value in new_data.items():
            current_value = getattr(school, field)
            
            # Handle decimal comparison
            if field in ['latitude', 'longitude'] and current_value is not None and new_value is not None:
                try:
                    if abs(float(current_value) - float(new_value)) > 0.0000001:
                        return True
                except (ValueError, TypeError):
                    if str(current_value) != str(new_value):
                        return True
            elif current_value != new_value:
                return True
        
        return False
    
    @transaction.atomic
    def sync_schools(self, records, is_dry_run, options):
        """
        Sync school records from Airtable
        - Add new schools
        - Update existing schools
        - Never delete schools (to preserve relationships)
        """
        self.stdout.write(f"Starting sync of {len(records)} school records...\n")
        
        # Initialize counters
        stats = {
            'processed': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'unchanged': 0,
            'linked': 0,
        }
        
        # Track details for verbose output
        details = {
            'created_schools': [],
            'updated_schools': [],
            'skipped_schools': [],
            'unchanged_schools': [],
            'linked_schools': [],
        }
        
        # Process each record
        for i, record in enumerate(records):
            stats['processed'] += 1
            
            # Log progress every 10 records
            if i % 10 == 0 and i > 0:
                self.stdout.write(f"Processing record {i+1} of {len(records)}...")
            
            airtable_id = record['id']
            fields = record.get('fields', {})
            
            # Extract school name - REQUIRED field
            school_name = self.extract_value(fields.get('School'))
            if not school_name:
                details['skipped_schools'].append({
                    'airtable_id': airtable_id,
                    'reason': 'Missing school name'
                })
                stats['skipped'] += 1
                if options['verbose']:
                    self.stdout.write(self.style.WARNING(f"  Skipping record {airtable_id}: Missing school name"))
                continue
            
            # Extract all other fields from Airtable
            # Type is a multiple select field in Airtable
            school_type_raw = fields.get('Type')  # Don't extract_value - keep as list
            school_type = self.map_airtable_school_type(school_type_raw)
            
            # Principal (just a text field)
            principal = self.extract_value(fields.get('Principal'))
            
            # Contact information
            contact_person = self.extract_value(fields.get('Main Contact'))
            contact_phone = self.format_phone_number(self.extract_value(fields.get('Main Contact Phone Number')))
            
            # Note: No email field in this Airtable schema
            
            # Location information
            address = self.extract_value(fields.get('Address'))
            suburb = self.extract_value(fields.get('Suburb'))
            city = self.extract_value(fields.get('City'))
            
            # If we have a suburb, append it to address
            if suburb and address:
                address = f"{address}, {suburb}"
            elif suburb and not address:
                address = suburb
            
            # Coordinates - direct fields in Airtable
            latitude = fields.get('Coord East')  # Note: "East" is actually latitude
            longitude = fields.get('Coord South')  # Note: "South" is actually longitude
            
            # Programmes (multiple select field - store as comma-separated)
            programmes = fields.get('Programmes')
            if programmes and isinstance(programmes, list):
                site_type = ', '.join(programmes)
            elif programmes:
                site_type = str(programmes)
            else:
                site_type = None
            
            # Actively Working In (boolean checkbox in Airtable)
            actively_working_raw = fields.get('Actively Working In')
            # Convert boolean to string that fits in varchar(5): "Yes"/"No"
            if actively_working_raw is True:
                actively_working = 'Yes'
            elif actively_working_raw is False:
                actively_working = 'No'
            else:
                actively_working = None
            
            # Prepare the data dictionary
            school_data = {
                'name': school_name,
                'type': school_type,
                'site_type': site_type,
                'contact_person': contact_person,
                'contact_phone': contact_phone,
                'principal': principal,
                'city': city,
                'address': address,
                'latitude': latitude,
                'longitude': longitude,
                'actively_working_in': actively_working,
                'is_active': True,  # Assume schools from Airtable are active
            }
            
            # Remove None values to avoid overwriting existing data with blanks
            # (only update fields that have actual values from Airtable)
            school_data = {k: v for k, v in school_data.items() if v is not None}
            
            try:
                # Check if school already exists by airtable_id
                existing_school = School.objects.filter(airtable_id=airtable_id).first()
                
                # If not found by airtable_id and --link-existing flag is set, try to find by name
                if not existing_school and options.get('link_existing'):
                    # Case-insensitive name match, strip whitespace
                    existing_school = School.objects.filter(
                        name__iexact=school_name.strip()
                    ).filter(
                        airtable_id__isnull=True  # Only match schools without airtable_id
                    ).first()
                    
                    if existing_school:
                        # Link this school to Airtable
                        stats['linked'] += 1
                        
                        if not is_dry_run:
                            existing_school.airtable_id = airtable_id
                            existing_school.save()
                        
                        details['linked_schools'].append({
                            'id': existing_school.id,
                            'name': school_name,
                            'airtable_id': airtable_id
                        })
                        
                        if options['verbose']:
                            self.stdout.write(self.style.SUCCESS(
                                f"  {'[DRY RUN] Would link' if is_dry_run else 'Linked'} existing school to Airtable: {school_name} (Django ID: {existing_school.id})"
                            ))
                
                if existing_school:
                    # Check if any fields have actually changed
                    if self.has_changes(existing_school, school_data):
                        if not is_dry_run:
                            # Update existing school
                            for field, value in school_data.items():
                                setattr(existing_school, field, value)
                            existing_school.save()
                        
                        stats['updated'] += 1
                        details['updated_schools'].append({
                            'id': existing_school.id,
                            'airtable_id': airtable_id,
                            'name': school_name,
                            'changes': school_data
                        })
                        
                        if options['verbose']:
                            change_summary = ', '.join([f"{k}={v}" for k, v in school_data.items()])
                            self.stdout.write(self.style.SUCCESS(
                                f"  {'[DRY RUN] Would update' if is_dry_run else 'Updated'} school: {school_name} ({change_summary})"
                            ))
                    else:
                        stats['unchanged'] += 1
                        details['unchanged_schools'].append({
                            'id': existing_school.id,
                            'airtable_id': airtable_id,
                            'name': school_name
                        })
                        
                        if options['verbose']:
                            self.stdout.write(f"  No changes needed for school: {school_name}")
                else:
                    # Create new school
                    if not is_dry_run:
                        new_school = School.objects.create(
                            airtable_id=airtable_id,
                            **school_data
                        )
                        school_id = new_school.id
                    else:
                        school_id = 'N/A (dry run)'
                    
                    stats['created'] += 1
                    details['created_schools'].append({
                        'id': school_id,
                        'airtable_id': airtable_id,
                        'name': school_name,
                        'data': school_data
                    })
                    
                    if options['verbose']:
                        self.stdout.write(self.style.SUCCESS(
                            f"  {'[DRY RUN] Would create' if is_dry_run else 'Created'} new school: {school_name}"
                        ))
                
            except Exception as e:
                stats['skipped'] += 1
                details['skipped_schools'].append({
                    'airtable_id': airtable_id,
                    'name': school_name,
                    'reason': str(e)
                })
                self.stdout.write(self.style.ERROR(
                    f"  Error processing school {school_name} (Airtable ID: {airtable_id}): {str(e)}"
                ))
        
        # Print detailed summary
        self.stdout.write("\n" + "="*60)
        
        if details['linked_schools']:
            self.stdout.write(self.style.SUCCESS(f"\nLinked Existing Schools to Airtable ({len(details['linked_schools'])}):"))
            for school in details['linked_schools']:
                self.stdout.write(f"  - {school['name']} (Django ID: {school['id']}, Airtable ID: {school['airtable_id']})")
        
        if details['created_schools']:
            self.stdout.write(self.style.SUCCESS(f"\nCreated Schools ({len(details['created_schools'])}):"))
            for school in details['created_schools'][:20]:  # Show first 20
                self.stdout.write(f"  - {school['name']} (Airtable ID: {school['airtable_id']})")
            if len(details['created_schools']) > 20:
                self.stdout.write(f"  ... and {len(details['created_schools']) - 20} more")
        
        if details['updated_schools']:
            self.stdout.write(self.style.SUCCESS(f"\nUpdated Schools ({len(details['updated_schools'])}):"))
            for school in details['updated_schools'][:20]:  # Show first 20
                self.stdout.write(f"  - {school['name']} (Airtable ID: {school['airtable_id']})")
            if len(details['updated_schools']) > 20:
                self.stdout.write(f"  ... and {len(details['updated_schools']) - 20} more")
        
        if details['skipped_schools']:
            self.stdout.write(self.style.WARNING(f"\nSkipped Schools ({len(details['skipped_schools'])}):"))
            for school in details['skipped_schools']:
                self.stdout.write(f"  - {school.get('name', 'N/A')} (Airtable ID: {school['airtable_id']}): {school['reason']}")
        
        return stats

