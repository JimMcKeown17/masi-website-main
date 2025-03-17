import os
import requests
import pandas as pd
from dashboards.utils.text_utils import clean_text, parse_date

def get_airtable_credentials():
    """Retrieve Airtable credentials from environment variables"""
    base_id = os.getenv('AIRTABLE_YOUTH_BASE_ID')
    api_key = os.getenv('AIRTABLE_API_KEY')
    table_id = os.getenv('AIRTABLE_COMBINED_YOUTH_DATA_TABLE_ID')
    
    # Check if environment variables are set
    missing_vars = []
    if not base_id:
        missing_vars.append('AIRTABLE_YOUTH_BASE_ID')
    if not api_key:
        missing_vars.append('AIRTABLE_API_KEY')
    if not table_id:
        missing_vars.append('AIRTABLE_COMBINED_YOUTH_DATA_TABLE_ID')
    
    if missing_vars:
        return None, f"Missing environment variables: {', '.join(missing_vars)}"
    
    return {
        'base_id': base_id,
        'api_key': api_key,
        'table_id': table_id
    }, None

def fetch_airtable_records():
    """Fetch all records from Airtable table"""
    credentials, error = get_airtable_credentials()
    if error:
        return None, error
    
    # Construct Airtable API URL
    url = f'https://api.airtable.com/v0/{credentials["base_id"]}/{credentials["table_id"]}'
    
    # Set up headers with API key
    headers = {
        'Authorization': f'Bearer {credentials["api_key"]}',
        'Content-Type': 'application/json'
    }
    
    try:
        # Fetch all records with pagination
        all_records = []
        params = {}
        
        while True:
            # Fetch page of records
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            # Parse the JSON response
            data = response.json()
            
            # Add records from this page
            page_records = data.get('records', [])
            all_records.extend(page_records)
            print(f"Fetched {len(page_records)} records. Total so far: {len(all_records)}")
            
            # Check if there are more pages
            if 'offset' in data:
                params['offset'] = data['offset']
            else:
                break
        
        print(f"\nTotal records fetched: {len(all_records)}")
        return all_records, None
        
    except requests.exceptions.RequestException as req_err:
        return None, f"Error connecting to Airtable API: {req_err}"
    except Exception as err:
        return None, f"An unexpected error occurred: {err}"