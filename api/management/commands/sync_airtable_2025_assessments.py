import os
import json
import time
import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from api.models import Assessment2025, AirtableSyncLog


class Command(BaseCommand):
    help = 'Sync 2025 assessments from Airtable - update existing and add new records'

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
            '--local-file',
            type=str,
            help='Path to local JSON file (defaults to data_exports/airtable_2025_assessments.json)',
        )

    def handle(self, *args, **options):
        is_dry_run = options['dry_run']
        
        # Start a new sync log (only if not dry-run)
        if not is_dry_run:
            sync_log = AirtableSyncLog.objects.create(sync_type='2025_assessments')
            self.stdout.write(self.style.SUCCESS(f'Starting 2025 assessments sync (ID: {sync_log.id})...'))
        else:
            sync_log = None
            self.stdout.write(self.style.WARNING('=== DRY RUN MODE - No changes will be saved ===\n'))
        
        try:
            # Get data source (local file or API)
            if options['local']:
                records = self.get_data_from_file(options.get('local_file'))
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
                
            # Sync the assessments
            stats = self.sync_assessments(records, is_dry_run, options)
            
            # Mark the sync as complete
            if sync_log:
                sync_log.records_created = stats['created']
                sync_log.records_updated = stats['updated']
                sync_log.records_skipped = stats['skipped']
                sync_log.records_processed = stats['processed']
                sync_log.mark_complete(success=True)
            
            # Print summary
            if is_dry_run:
                self.stdout.write(self.style.WARNING('\n=== DRY RUN COMPLETE - No changes were saved ==='))
            else:
                self.stdout.write(self.style.SUCCESS('\n=== SYNC COMPLETED SUCCESSFULLY ==='))
            
            self.stdout.write(f'Processed: {stats["processed"]}')
            self.stdout.write(f'Created: {stats["created"]}')
            self.stdout.write(f'Updated: {stats["updated"]}')
            self.stdout.write(f'Skipped: {stats["skipped"]}')
            self.stdout.write(f'No changes needed: {stats["unchanged"]}')
                
        except Exception as e:
            # Log the error and mark sync as failed
            if sync_log:
                sync_log.mark_complete(success=False, error_message=str(e))
            self.stdout.write(self.style.ERROR(f'Error during 2025 assessments sync: {str(e)}'))
            raise
    
    def get_data_from_file(self, file_path=None):
        """Get assessments data from a local JSON file"""
        if file_path:
            data_file = file_path
        else:
            data_file = os.path.join(settings.BASE_DIR, 'data_exports', 'airtable_2025_assessments.json')
        
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
        """Fetch 2025 assessments data directly from Airtable API"""
        self.stdout.write("Fetching data from Airtable API...")
        
        # Get Airtable API key and base/table IDs from environment variables
        api_key = os.environ.get('AIRTABLE_API_KEY')
        base_id = os.environ.get('AIRTABLE_2025_ASSESSMENTS_BASE_ID')
        table_id = os.environ.get('AIRTABLE_2025_ASSESSMENTS_TABLE_ID')
        
        # Check if environment variables are set
        if not api_key:
            raise ValueError('AIRTABLE_API_KEY not found in environment variables')
        if not base_id:
            raise ValueError('AIRTABLE_2025_ASSESSMENTS_BASE_ID not found in environment variables')
        if not table_id:
            raise ValueError('AIRTABLE_2025_ASSESSMENTS_TABLE_ID not found in environment variables')
        
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
    
    def safe_str(self, value):
        """Safely convert value to string, return None if empty"""
        if value is None:
            return None
        if isinstance(value, list):
            # Handle lookup fields that return arrays
            return value[0] if len(value) > 0 else None
        result = str(value).strip()
        return result if result else None
    
    def safe_int(self, value):
        """Safely convert value to int, return None if invalid"""
        if value is None:
            return None
        if isinstance(value, list):
            value = value[0] if len(value) > 0 else None
        if value is None or str(value).strip() == '':
            return None
        try:
            return int(float(str(value).strip()))
        except (ValueError, TypeError):
            return None
    
    def map_fields(self, fields):
        """Map Airtable fields to Assessment2025 model fields"""
        return {
            # Core identification
            'mcode': self.safe_str(fields.get('Mcode')),
            'surname': self.safe_str(fields.get('Surname')),
            'name': self.safe_str(fields.get('Name')),
            'full_name': self.safe_str(fields.get('Full Name')),
            
            # Demographics
            'gender': self.safe_str(fields.get('Gender')),
            'race': self.safe_str(fields.get('Race')),
            'language': self.safe_str(fields.get('Language')),
            
            # School/Class info
            'school': self.safe_str(fields.get('School')),
            'city': self.safe_str(fields.get('City')),
            'grade': self.safe_str(fields.get('Grade')),
            'class_name': self.safe_str(fields.get('Class')),
            'teacher': self.safe_str(fields.get('Teacher')),
            'centre_type': self.safe_str(fields.get('Centre Type')),
            'mentor': self.safe_str(fields.get('Mentor')),
            
            # Program participation
            'on_programme': self.safe_str(fields.get('On the Programme')),
            'capturer': self.safe_str(fields.get('Capturer')),
            
            # Status fields
            'baseline_status': self.safe_str(fields.get('Baseline Status')),
            'midline_status': self.safe_str(fields.get('Midline Status')),
            'endline_status': self.safe_str(fields.get('Endline Status')),
            
            # January Assessment Scores (Baseline)
            'jan_letter_sounds': self.safe_int(fields.get('Jan - Letter Sounds')),
            'jan_story_comprehension': self.safe_int(fields.get('Jan - Story Comprehension')),
            'jan_listen_first_sound': self.safe_int(fields.get('Jan - Listen First Sound')),
            'jan_listen_words': self.safe_int(fields.get('Jan - Listen Words')),
            'jan_writing_letters': self.safe_int(fields.get('Jan - Writing Letters')),
            'jan_read_words': self.safe_int(fields.get('Jan - Read Words')),
            'jan_read_sentences': self.safe_int(fields.get('Jan - Read Sentences')),
            'jan_read_story': self.safe_int(fields.get('Jan - Read Story')),
            'jan_write_cvcs': self.safe_int(fields.get('Jan - Write CVCs')),
            'jan_write_sentences': self.safe_int(fields.get('Jan - Write Sentences')),
            'jan_write_story': self.safe_int(fields.get('Jan - Write Story')),
            'jan_total': self.safe_int(fields.get('Jan - Total')),
            
            # June Assessment Scores (Midline)
            'june_letter_sounds': self.safe_int(fields.get('June - Letter Sounds')),
            'june_story_comprehension': self.safe_int(fields.get('June - Story Comprehension')),
            'june_listen_first_sound': self.safe_int(fields.get('June - Listen First Sound')),
            'june_listen_words': self.safe_int(fields.get('June - Listen Words')),
            'june_writing_letters': self.safe_int(fields.get('June - Writing Letters')),
            'june_read_words': self.safe_int(fields.get('June - Read Words')),
            'june_read_sentences': self.safe_int(fields.get('June - Read Sentences')),
            'june_read_story': self.safe_int(fields.get('June - Read Story')),
            'june_write_cvcs': self.safe_int(fields.get('June - Write CVCs')),
            'june_write_sentences': self.safe_int(fields.get('June - Write Sentences')),
            'june_write_story': self.safe_int(fields.get('June - Write Story')),
            'june_total': self.safe_int(fields.get('June - Total')),
            
            # November Assessment Scores (Endline)
            'nov_letter_sounds': self.safe_int(fields.get('Nov - Letter Sounds')),
            'nov_story_comprehension': self.safe_int(fields.get('Nov - Story Comprehension')),
            'nov_listen_first_sound': self.safe_int(fields.get('Nov - Listen First Sound')),
            'nov_listen_words': self.safe_int(fields.get('Nov - Listen Words')),
            'nov_writing_letters': self.safe_int(fields.get('Nov - Writing Letters')),
            'nov_read_words': self.safe_int(fields.get('Nov - Read Words')),
            'nov_read_sentences': self.safe_int(fields.get('Nov - Read Sentences')),
            'nov_read_story': self.safe_int(fields.get('Nov - Read Story')),
            # Note: Airtable field has typo "Nov- Write CVCs" (no space after Nov)
            'nov_write_cvcs': self.safe_int(fields.get('Nov- Write CVCs') or fields.get('Nov - Write CVCs')),
            'nov_write_sentences': self.safe_int(fields.get('Nov - Write Sentences')),
            'nov_write_story': self.safe_int(fields.get('Nov - Write Story')),
            'nov_total': self.safe_int(fields.get('Nov - Total')),
        }
    
    def has_changes(self, assessment, new_data):
        """Check if any fields would be changed"""
        for field, new_value in new_data.items():
            if new_value is None:
                continue  # Skip None values - don't overwrite existing with blank
            current_value = getattr(assessment, field)
            if current_value != new_value:
                return True
        return False
    
    def get_changed_fields(self, assessment, new_data):
        """Get list of fields that have changed"""
        changed = {}
        for field, new_value in new_data.items():
            if new_value is None:
                continue
            current_value = getattr(assessment, field)
            if current_value != new_value:
                changed[field] = {'old': current_value, 'new': new_value}
        return changed

    def sync_assessments(self, records, is_dry_run, options):
        """
        Sync assessment records from Airtable
        - Add new assessments
        - Update existing assessments (matched by airtable_id)
        
        Note: Each record is processed independently (no global transaction)
        so that one failure doesn't affect other records.
        """
        self.stdout.write(f"Starting sync of {len(records)} assessment records...\n")
        
        # Initialize counters
        stats = {
            'processed': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'unchanged': 0,
        }
        
        # Track details for verbose output
        details = {
            'created_assessments': [],
            'updated_assessments': [],
            'skipped_assessments': [],
            'unchanged_assessments': [],
        }
        
        # Process each record
        for i, record in enumerate(records):
            stats['processed'] += 1
            
            # Log progress every 100 records
            if i % 100 == 0 and i > 0:
                self.stdout.write(f"Processing record {i+1} of {len(records)}... (Created: {stats['created']}, Updated: {stats['updated']})")
            
            airtable_id = record.get('id')
            if not airtable_id:
                stats['skipped'] += 1
                details['skipped_assessments'].append({
                    'reason': 'Missing Airtable ID'
                })
                continue
                
            fields = record.get('fields', {})
            
            # Map Airtable fields to model fields
            assessment_data = self.map_fields(fields)
            
            # Remove None values to avoid overwriting existing data with blanks
            assessment_data = {k: v for k, v in assessment_data.items() if v is not None}
            
            try:
                # Use individual transaction for each record
                with transaction.atomic():
                    # Check if assessment already exists by airtable_id
                    existing_assessment = Assessment2025.objects.filter(airtable_id=airtable_id).first()
                    
                    if existing_assessment:
                        # Check if any fields have actually changed
                        if self.has_changes(existing_assessment, assessment_data):
                            changed_fields = self.get_changed_fields(existing_assessment, assessment_data)
                            
                            if not is_dry_run:
                                # Update existing assessment
                                for field, value in assessment_data.items():
                                    setattr(existing_assessment, field, value)
                                existing_assessment.save()
                            
                            stats['updated'] += 1
                            details['updated_assessments'].append({
                                'id': existing_assessment.id,
                                'airtable_id': airtable_id,
                                'full_name': assessment_data.get('full_name', existing_assessment.full_name),
                                'mcode': assessment_data.get('mcode', existing_assessment.mcode),
                                'changes': changed_fields
                            })
                            
                            if options['verbose']:
                                name = assessment_data.get('full_name', existing_assessment.full_name or 'Unknown')
                                self.stdout.write(self.style.SUCCESS(
                                    f"  {'[DRY RUN] Would update' if is_dry_run else 'Updated'}: {name} - {len(changed_fields)} field(s) changed"
                                ))
                        else:
                            stats['unchanged'] += 1
                            details['unchanged_assessments'].append({
                                'id': existing_assessment.id,
                                'airtable_id': airtable_id,
                                'full_name': existing_assessment.full_name
                            })
                    else:
                        # Create new assessment
                        if not is_dry_run:
                            new_assessment = Assessment2025.objects.create(
                                airtable_id=airtable_id,
                                **assessment_data
                            )
                            assessment_id = new_assessment.id
                        else:
                            assessment_id = 'N/A (dry run)'
                        
                        stats['created'] += 1
                        details['created_assessments'].append({
                            'id': assessment_id,
                            'airtable_id': airtable_id,
                            'full_name': assessment_data.get('full_name'),
                            'mcode': assessment_data.get('mcode'),
                            'school': assessment_data.get('school'),
                        })
                        
                        if options['verbose']:
                            name = assessment_data.get('full_name', 'Unknown')
                            school = assessment_data.get('school', 'Unknown School')
                            self.stdout.write(self.style.SUCCESS(
                                f"  {'[DRY RUN] Would create' if is_dry_run else 'Created'}: {name} ({school})"
                            ))
                
            except Exception as e:
                stats['skipped'] += 1
                details['skipped_assessments'].append({
                    'airtable_id': airtable_id,
                    'full_name': assessment_data.get('full_name'),
                    'reason': str(e)
                })
                if options['verbose']:
                    self.stdout.write(self.style.ERROR(
                        f"  Error processing record {airtable_id}: {str(e)}"
                    ))
        
        # Print detailed summary
        self.stdout.write("\n" + "="*60)
        
        if details['created_assessments']:
            self.stdout.write(self.style.SUCCESS(f"\nCreated Assessments ({len(details['created_assessments'])}):"))
            for assessment in details['created_assessments'][:20]:  # Show first 20
                name = assessment.get('full_name', 'Unknown')
                school = assessment.get('school', 'Unknown')
                self.stdout.write(f"  - {name} ({school})")
            if len(details['created_assessments']) > 20:
                self.stdout.write(f"  ... and {len(details['created_assessments']) - 20} more")
        
        if details['updated_assessments']:
            self.stdout.write(self.style.SUCCESS(f"\nUpdated Assessments ({len(details['updated_assessments'])}):"))
            for assessment in details['updated_assessments'][:20]:  # Show first 20
                name = assessment.get('full_name', 'Unknown')
                num_changes = len(assessment.get('changes', {}))
                self.stdout.write(f"  - {name} ({num_changes} field(s) changed)")
            if len(details['updated_assessments']) > 20:
                self.stdout.write(f"  ... and {len(details['updated_assessments']) - 20} more")
        
        if details['skipped_assessments']:
            self.stdout.write(self.style.WARNING(f"\nSkipped Assessments ({len(details['skipped_assessments'])}):"))
            for assessment in details['skipped_assessments'][:10]:  # Show first 10
                name = assessment.get('full_name', 'N/A')
                reason = assessment.get('reason', 'Unknown')
                self.stdout.write(f"  - {name}: {reason}")
            if len(details['skipped_assessments']) > 10:
                self.stdout.write(f"  ... and {len(details['skipped_assessments']) - 10} more")
        
        if stats['unchanged'] > 0:
            self.stdout.write(f"\nNo changes needed: {stats['unchanged']} records")
        
        return stats

