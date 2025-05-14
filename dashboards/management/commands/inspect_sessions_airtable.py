import os
import json
import requests
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Fetch session data from Airtable API and save to a JSON file for inspection'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting to fetch Airtable sessions data...'))
        
        # Get Airtable API key and base/table IDs from environment variables
        api_key = os.environ.get('AIRTABLE_API_KEY')
        base_id = os.environ.get('AIRTABLE_SESSIONS_BASE_ID')
        table_id = os.environ.get('AIRTABLE_SESSIONS_TABLE_ID')
        
        # Check if environment variables are set
        if not api_key:
            self.stdout.write(self.style.ERROR('Airtable API key not found in environment variables. Make sure AIRTABLE_API_KEY is set.'))
            return
        if not base_id:
            self.stdout.write(self.style.ERROR('Airtable base ID not found in environment variables. Make sure AIRTABLE_SESSIONS_BASE_ID is set.'))
            return
        if not table_id:
            self.stdout.write(self.style.ERROR('Airtable table ID not found in environment variables. Make sure AIRTABLE_SESSIONS_TABLE_ID is set.'))
            return
        
        # Construct the API URL
        url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
        
        # Set up headers with API key
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Initialize empty list for all records
        all_records = []
        
        try:
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
                    self.stdout.write(self.style.ERROR(
                        f"Error fetching data from Airtable: {response.status_code} - {response.text}"
                    ))
                    return
                
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
            
            # Save all records to a JSON file
            output_dir = os.path.join(settings.BASE_DIR, 'data_exports')
            
            # Create directory if it doesn't exist
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            output_file = os.path.join(output_dir, 'airtable_sessions_data.json')
            
            with open(output_file, 'w') as f:
                # Pretty print with indentation for readability
                json.dump(all_records, f, indent=2)
            
            # Save a sample file with just a few records for easier inspection
            if all_records:
                sample_records = all_records[:5]  # Get first 5 records as sample
                sample_file = os.path.join(output_dir, 'airtable_sessions_sample.json')
                
                with open(sample_file, 'w') as f:
                    json.dump(sample_records, f, indent=2)
                
                self.stdout.write(self.style.SUCCESS(
                    f"Sample data (5 records) saved to {sample_file}"
                ))
            
            # Print summary and data structure info
            if all_records:
                # Get the fields from the first record to understand structure
                first_record = all_records[0]
                fields = first_record.get('fields', {})
                field_names = list(fields.keys())
                
                self.stdout.write(self.style.SUCCESS(
                    f"Successfully fetched {record_count} records from {page_count} pages"
                ))
                self.stdout.write(self.style.SUCCESS(f"Data saved to {output_file}"))
                
                self.stdout.write("\nField names in the data:")
                for i, field in enumerate(field_names, 1):
                    self.stdout.write(f"  {i}. {field}")
                
                # Get data types for each field based on first record
                self.stdout.write("\nField data types (based on first record):")
                for field, value in fields.items():
                    data_type = type(value).__name__
                    sample = str(value)
                    if isinstance(value, str) and len(sample) > 50:
                        sample = sample[:50] + "..."
                    elif isinstance(value, list) and len(sample) > 50:
                        sample = f"List with {len(value)} items"
                    
                    self.stdout.write(f"  {field}: {data_type} - Example: {sample}")
            else:
                self.stdout.write(self.style.SUCCESS("No records found in the table"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))