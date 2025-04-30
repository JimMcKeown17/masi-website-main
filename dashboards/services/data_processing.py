import pandas as pd
from dashboards.utils.text_utils import clean_text, parse_date
from datetime import datetime

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
    
    # Ensure Age is numeric
    if 'Age' in df.columns:
        df['Age'] = pd.to_numeric(df['Age'], errors='coerce')
    
    # Calculate months active
    df = calculate_months_active(df)
    
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

def calculate_months_active(df):
    """
    Calculate months active based on employment status and dates.
    
    For active employees: today's date - start date
    For inactive employees: end date - start date
    
    Args:
        df: DataFrame containing 'Employment Status', 'Start Date', and 'End Date' columns
        
    Returns:
        DataFrame with added 'Months Active' column
    """
    if df is None or df.empty:
        return None
    
    # Ensure we have the required columns
    required_columns = ['Employment Status', 'Start Date']
    if not all(col in df.columns for col in required_columns):
        return None
    
    # Make a copy to avoid modifying the original
    df = df.copy()
    
    # Convert dates to datetime if they aren't already
    df['Start Date'] = pd.to_datetime(df['Start Date'])
    if 'End Date' in df.columns:
        df['End Date'] = pd.to_datetime(df['End Date'])
    
    # Calculate months active
    def calculate_months(row):
        if pd.isna(row['Start Date']):
            return None
            
        if row['Employment Status'] == 'Active':
            end_date = datetime.now()
        else:
            end_date = row['End Date'] if 'End Date' in row and not pd.isna(row['End Date']) else datetime.now()
            
        if pd.isna(end_date):
            return None
            
        # Calculate months difference
        months = (end_date.year - row['Start Date'].year) * 12 + (end_date.month - row['Start Date'].month)
        return max(0, months)  # Ensure non-negative
    
    df['Months Active'] = df.apply(calculate_months, axis=1)
    return df