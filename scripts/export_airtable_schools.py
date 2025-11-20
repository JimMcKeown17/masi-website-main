"""
Helper script to export Airtable schools data to a local JSON file.
This is useful for testing the sync script without hitting the API repeatedly.

Usage:
    python scripts/export_airtable_schools.py

Requirements:
    - AIRTABLE_API_KEY environment variable
    - AIRTABLE_SCHOOLS_BASE_ID environment variable
    - AIRTABLE_SCHOOLS_TABLE_ID environment variable
"""

import os
import sys
import json
import time
import requests
from datetime import datetime
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Get the project root directory (parent of scripts/)
    project_root = Path(__file__).parent.parent
    env_path = project_root / '.env'
    
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment variables from: {env_path}\n")
    else:
        print(f"Warning: .env file not found at {env_path}")
        print("Make sure environment variables are set in your shell.\n")
except ImportError:
    print("Warning: python-dotenv not installed.")
    print("Install with: pip install python-dotenv")
    print("Or set environment variables manually in your shell.\n")

def fetch_all_schools():
    """Fetch all schools from Airtable"""
    
    # Get environment variables
    api_key = os.environ.get('AIRTABLE_API_KEY')
    base_id = os.environ.get('AIRTABLE_SCHOOLS_BASE_ID')
    table_id = os.environ.get('AIRTABLE_SCHOOLS_TABLE_ID')
    
    if not all([api_key, base_id, table_id]):
        print("ERROR: Missing environment variables!")
        print(f"  AIRTABLE_API_KEY: {'✓' if api_key else '✗'}")
        print(f"  AIRTABLE_SCHOOLS_BASE_ID: {'✓' if base_id else '✗'}")
        print(f"  AIRTABLE_SCHOOLS_TABLE_ID: {'✓' if table_id else '✗'}")
        return None
    
    # Construct URL
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    all_records = []
    params = {"pageSize": 100}
    page_count = 0
    
    print("Fetching schools from Airtable...")
    
    while True:
        page_count += 1
        print(f"  Fetching page {page_count}...")
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            print(f"ERROR: API request failed with status {response.status_code}")
            print(response.text)
            return None
        
        data = response.json()
        page_records = data.get('records', [])
        all_records.extend(page_records)
        
        print(f"    Got {len(page_records)} records")
        
        # Check for more pages
        offset = data.get('offset')
        if not offset:
            break
        
        params['offset'] = offset
        time.sleep(0.2)  # Rate limiting
    
    print(f"\nTotal records fetched: {len(all_records)}")
    return all_records

def save_to_file(records, output_dir='data_exports'):
    """Save records to JSON file"""
    
    # Create directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'airtable_schools_data.json'
    filepath = os.path.join(output_dir, filename)
    
    # Also create a timestamped backup
    backup_filename = f'airtable_schools_data_{timestamp}.json'
    backup_filepath = os.path.join(output_dir, backup_filename)
    
    # Save the data
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    
    with open(backup_filepath, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    
    print(f"\nData saved to:")
    print(f"  - {filepath}")
    print(f"  - {backup_filepath} (backup)")
    
    return filepath

def print_summary(records):
    """Print a summary of the exported data"""
    if not records:
        return
    
    print("\n" + "="*60)
    print("EXPORT SUMMARY")
    print("="*60)
    
    print(f"Total schools: {len(records)}")
    
    # Count schools by type
    school_types = {}
    cities = {}
    
    for record in records:
        fields = record.get('fields', {})
        
        school_type = fields.get('School Type')
        if isinstance(school_type, list) and school_type:
            school_type = school_type[0]
        if school_type:
            school_types[school_type] = school_types.get(school_type, 0) + 1
        
        city = fields.get('City')
        if isinstance(city, list) and city:
            city = city[0]
        if city:
            cities[city] = cities.get(city, 0) + 1
    
    if school_types:
        print("\nSchools by type:")
        for school_type, count in sorted(school_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {school_type}: {count}")
    
    if cities:
        print("\nTop 10 cities:")
        for city, count in sorted(cities.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  - {city}: {count}")
    
    # Show sample record
    if records:
        print("\nSample record (first school):")
        first_record = records[0]
        fields = first_record.get('fields', {})
        print(f"  ID: {first_record['id']}")
        print(f"  Name: {fields.get('School/ Center Name', 'N/A')}")
        print(f"  Type: {fields.get('School Type', 'N/A')}")
        print(f"  City: {fields.get('City', 'N/A')}")
        print(f"  Available fields: {', '.join(sorted(fields.keys()))}")

def main():
    print("="*60)
    print("Airtable Schools Export Tool")
    print("="*60 + "\n")
    
    # Fetch data
    records = fetch_all_schools()
    
    if not records:
        print("\nExport failed!")
        return 1
    
    # Save to file
    filepath = save_to_file(records)
    
    # Print summary
    print_summary(records)
    
    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("\nYou can now test the sync script using this local data:")
    print("\n  python manage.py sync_airtable_schools --local --dry-run --verbose")
    print("\nThis will preview changes without touching the database.")
    print("\n" + "="*60)
    
    return 0

if __name__ == '__main__':
    exit(main())

