import pandas as pd
from dashboards.utils.text_utils import clean_text, parse_date

def process_airtable_records(records):
    """Transform raw Airtable records into a clean DataFrame"""
    if not records:
        return None
    
    # Transform records with careful cleaning
    records_list = []
    for record in records:
        record_data = {'record_id': record['id']}
        
        # Clean each field
        for key, value in record['fields'].items():
            try:
                # Special handling for known date fields
                if key in ['Start Date', 'End Date']:
                    record_data[key] = parse_date(value)
                else:
                    record_data[key] = clean_text(value)
            except Exception as field_err:
                print(f"Error processing field '{key}': {field_err}, value type: {type(value)}")
                record_data[key] = None
        
        records_list.append(record_data)
    
    # Convert to DataFrame
    df = pd.DataFrame(records_list)
    return df

def get_active_records(df):
    """Filter for active records in the DataFrame"""
    if df is None or df.empty or 'Employment Status' not in df.columns:
        return None
    
    # Check if Employment Status is coming as a string representation of a list
    if all(isinstance(status, str) and status.startswith('[') for status in df['Employment Status'].dropna()):
        print("Employment status appears to be a string representation of a list")
        # Filter for records containing 'Active'
        active_df = df[df['Employment Status'].str.contains('Active', na=False)]
    else:
        # Standard filter for exact match
        active_df = df[df['Employment Status'] == 'Active']
    
    return active_df

def count_job_titles(df):
    """Count job titles from DataFrame"""
    if df is None or df.empty or 'Job Title' not in df.columns:
        return None
    
    return df['Job Title'].value_counts()