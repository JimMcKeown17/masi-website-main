import os
import requests
import pandas as pd
from django.conf import settings

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
    if not records:
        return pd.DataFrame()
    
    # Extract fields from each record
    data = []
    for record in records:
        # Get the fields dict from the record
        fields = record.get('fields', {})
        
        # Add record ID to fields
        fields['record_id'] = record.get('id')
        
        # Handle list values (e.g., from multi-select fields)
        for key, value in fields.items():
            if isinstance(value, list):
                # Join list values into a string, or use first item if applicable
                if len(value) == 1:
                    fields[key] = value[0]
                else:
                    fields[key] = ', '.join(str(v) for v in value)
        
        # Add to data list
        data.append(fields)
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    # Perform any necessary data cleaning or transformation
    # Convert date strings to datetime objects
    date_columns = ['Start Date', 'End Date', 'DOB']
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    
    # Calculate age from DOB if Age column doesn't exist
    if 'Age' not in df.columns and 'DOB' in df.columns:
        df['Age'] = (pd.Timestamp.now() - df['DOB']).dt.days // 365
    
    # Ensure Employment Status is clean
    if 'Employment Status' in df.columns:
        df['Employment Status'] = df['Employment Status'].fillna('Unknown')
    
    return df