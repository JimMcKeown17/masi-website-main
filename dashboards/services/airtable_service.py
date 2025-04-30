import os
import requests
import pandas as pd
from django.conf import settings
from dashboards.services.data_processing import process_airtable_records

def fetch_youth_airtable_records():
    """
    Fetch youth records from Airtable API
    
    Returns:
        Tuple of (records, error)
        where records is a list of youth records and error is None if successful,
        or records is None and error is an error message if unsuccessful
    """
    # Get Airtable API key and base ID from environment variables
    api_key = os.environ.get('AIRTABLE_API_KEY')
    base_id = os.environ.get('AIRTABLE_YOUTH_BASE_ID')
    table_id = os.environ.get('AIRTABLE_COMBINED_YOUTH_DATA_TABLE_ID')
    
    # Check if API key and base ID are set
    if not api_key:
        return None, "Airtable API key not found in environment variables. Make sure AIRTABLE_API_KEY is set."
    if not base_id:
        return None, "Airtable base ID not found in environment variables. Make sure AIRTABLE_BASE_ID is set."
    if not table_id:
        return None, "Airtable table ID not found in environment variables. Make sure AIRTABLE_COMBINED_YOUTH_DATA_TABLE_ID is set."
    
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
        # Airtable returns records in pages, so we need to handle pagination
        params = {"pageSize": 100}  # Maximum page size
        
        while True:
            # Make the API request
            response = requests.get(url, headers=headers, params=params)
            
            # Check if the request was successful
            if response.status_code != 200:
                return None, f"Error fetching data from Airtable: {response.status_code} - {response.text}"
            
            # Parse response as JSON
            data = response.json()
            
            # Add records to our list
            all_records.extend(data.get('records', []))
            
            # Check if there are more records
            offset = data.get('offset')
            if not offset:
                break
            
            # Update params with offset for next page
            params['offset'] = offset
        
        # Return the records
        return all_records, None
    
    except Exception as e:
        # Return an error message if an exception occurs
        return None, f"Error connecting to Airtable API: {str(e)}"

def process_youth_airtable_records(records):
    """
    Process youth records from Airtable API into a pandas DataFrame
    
    Args:
        records: List of records from Airtable API
        
    Returns:
        Pandas DataFrame with processed youth data
    """
    return process_airtable_records(records)