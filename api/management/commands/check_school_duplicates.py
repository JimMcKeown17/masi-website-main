"""
Django management command to check for potential school duplicates
between existing Django database and Airtable data.

This helps identify schools that exist in Django without airtable_id
that might be duplicated when syncing from Airtable.

Usage:
    python manage.py check_school_duplicates
    python manage.py check_school_duplicates --local  # Use local JSON file
"""

import os
import json
import requests
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db.models import Q

from api.models import School


class Command(BaseCommand):
    help = 'Check for potential school duplicates between Django database and Airtable'

    def add_arguments(self, parser):
        parser.add_argument(
            '--local',
            action='store_true',
            help='Use local JSON file instead of querying Airtable API',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Checking for potential school duplicates...\n'))
        
        # Get Airtable data
        if options['local']:
            airtable_records = self.get_data_from_file()
        else:
            airtable_records = self.fetch_from_airtable()
        
        if not airtable_records:
            self.stdout.write(self.style.ERROR('No Airtable records found.'))
            return
        
        # Get all Django schools
        django_schools = School.objects.all()
        
        self.stdout.write(f"Django Schools: {django_schools.count()}")
        self.stdout.write(f"Airtable Schools: {len(airtable_records)}\n")
        
        # Categorize Django schools
        schools_with_airtable_id = django_schools.filter(airtable_id__isnull=False)
        schools_without_airtable_id = django_schools.filter(airtable_id__isnull=True)
        
        self.stdout.write(f"Schools WITH airtable_id: {schools_with_airtable_id.count()}")
        self.stdout.write(f"Schools WITHOUT airtable_id: {schools_without_airtable_id.count()}\n")
        
        # Build dictionary of Airtable schools
        airtable_schools_dict = {}
        airtable_ids = set()
        
        for record in airtable_records:
            airtable_id = record['id']
            fields = record.get('fields', {})
            school_name = self.extract_value(fields.get('School'))
            
            if school_name:
                airtable_schools_dict[airtable_id] = school_name
                airtable_ids.add(airtable_id)
        
        # Check for potential duplicates
        self.stdout.write("="*80)
        self.stdout.write(self.style.WARNING("POTENTIAL DUPLICATES (by name matching):"))
        self.stdout.write("="*80 + "\n")
        
        potential_duplicates = []
        
        for django_school in schools_without_airtable_id:
            # Check if this school name exists in Airtable
            for airtable_id, airtable_name in airtable_schools_dict.items():
                # Case-insensitive comparison and strip whitespace
                if django_school.name.strip().lower() == airtable_name.strip().lower():
                    potential_duplicates.append({
                        'django_id': django_school.id,
                        'django_name': django_school.name,
                        'airtable_id': airtable_id,
                        'airtable_name': airtable_name,
                        'django_school': django_school
                    })
        
        if potential_duplicates:
            self.stdout.write(f"Found {len(potential_duplicates)} potential duplicates:\n")
            
            for dup in potential_duplicates:
                self.stdout.write(f"Django School:")
                self.stdout.write(f"  ID: {dup['django_id']}")
                self.stdout.write(f"  Name: {dup['django_name']}")
                self.stdout.write(f"  Airtable ID: None")
                self.stdout.write(f"  Has Youth: {dup['django_school'].youth.count()}")
                self.stdout.write(f"  Has Children: {dup['django_school'].children.count()}")
                self.stdout.write(f"  Has Visits: {dup['django_school'].visits.count()}")
                
                self.stdout.write(f"\nWould match Airtable School:")
                self.stdout.write(f"  Airtable ID: {dup['airtable_id']}")
                self.stdout.write(f"  Name: {dup['airtable_name']}")
                self.stdout.write("")
        else:
            self.stdout.write(self.style.SUCCESS("No potential duplicates found!\n"))
        
        # Check for already-linked schools
        self.stdout.write("="*80)
        self.stdout.write("SCHOOLS ALREADY LINKED TO AIRTABLE:")
        self.stdout.write("="*80 + "\n")
        
        already_linked = []
        for django_school in schools_with_airtable_id:
            if django_school.airtable_id in airtable_ids:
                already_linked.append(django_school)
        
        if already_linked:
            self.stdout.write(f"Found {len(already_linked)} schools already linked:\n")
            for school in already_linked[:10]:  # Show first 10
                self.stdout.write(f"  - {school.name} (Django ID: {school.id}, Airtable ID: {school.airtable_id})")
            if len(already_linked) > 10:
                self.stdout.write(f"  ... and {len(already_linked) - 10} more")
        else:
            self.stdout.write("No schools currently linked to Airtable.\n")
        
        # Summary and recommendations
        self.stdout.write("\n" + "="*80)
        self.stdout.write("SUMMARY AND RECOMMENDATIONS:")
        self.stdout.write("="*80 + "\n")
        
        if potential_duplicates:
            self.stdout.write(self.style.WARNING(
                f"⚠️  {len(potential_duplicates)} potential duplicate(s) detected!"
            ))
            self.stdout.write("\nRecommendations:")
            self.stdout.write("1. Use the --link-existing flag when running sync to link existing schools")
            self.stdout.write("   instead of creating duplicates:")
            self.stdout.write("   python manage.py sync_airtable_schools --link-existing --dry-run --verbose")
            self.stdout.write("\n2. Or manually update airtable_id for these schools in Django Admin")
            self.stdout.write("\n3. Run this check again after linking to verify")
        else:
            self.stdout.write(self.style.SUCCESS(
                "✅ No duplicates detected! Safe to run sync."
            ))
            
            if schools_without_airtable_id.count() > 0:
                self.stdout.write(f"\nNote: You have {schools_without_airtable_id.count()} school(s) without airtable_id.")
                self.stdout.write("These will not be updated by the sync (they're likely old/historical data).")
        
        self.stdout.write("")
    
    def extract_value(self, value):
        """Extract a single value from a potential list or return the value itself"""
        if isinstance(value, list) and len(value) > 0:
            return value[0]
        return value
    
    def get_data_from_file(self):
        """Get schools data from the local JSON file"""
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
        page_count = 0
        
        while True:
            # Make the API request
            page_count += 1
            response = requests.get(url, headers=headers, params=params)
            
            # Check if the request was successful
            if response.status_code != 200:
                raise ValueError(f"Error fetching data from Airtable: {response.status_code} - {response.text}")
            
            # Parse response as JSON
            data = response.json()
            
            # Get records from this page
            page_records = data.get('records', [])
            
            # Add records to our list
            all_records.extend(page_records)
            
            # Check if there are more records
            offset = data.get('offset')
            if not offset:
                break
            
            # Update params with offset for next page
            params['offset'] = offset
            
            # Add a slight delay to avoid hitting rate limits
            time.sleep(0.2)
        
        self.stdout.write(f"Fetched {len(all_records)} records\n")
        return all_records

