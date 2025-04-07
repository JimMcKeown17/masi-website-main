import json
from datetime import datetime
import pandas as pd
import numpy as np
from django.db.models import Count, Avg, Sum, Case, When, IntegerField, F
from django.db.models.functions import TruncMonth, TruncWeek

def ensure_string_values(df, column_name):
    """
    Ensure that values in a column are strings (not lists)
    
    Args:
        df: DataFrame
        column_name: Name of the column to check
        
    Returns:
        Modified DataFrame with string values in the specified column
    """
    if column_name in df.columns:
        # Make a copy to avoid modifying the original
        df = df.copy()
        
        # Convert any list values to strings
        df[column_name] = df[column_name].apply(
            lambda x: ', '.join(str(v) for v in x) if isinstance(x, list) else x
        )
    
    return df

def generate_youth_summary(df):
    """
    Generate summary statistics for the youth dashboard
    
    Args:
        df: DataFrame of youth data
        
    Returns:
        Dictionary of summary statistics
    """
    # Filter for active youth
    active_df = df[df['Employment Status'] == 'Active']
    
    # Calculate summary statistics
    summary = {
        'total_youth': len(df),
        'active_youth': len(active_df),
        'sites_count': active_df['Site Placement'].nunique(),
        'avg_age': active_df['Age'].mean(),
        'gender_ratio': {
            'male': (active_df['Gender'] == 'Male').sum() / len(active_df) * 100,
            'female': (active_df['Gender'] == 'Female').sum() / len(active_df) * 100,
        }
    }
    
    return summary

def generate_gender_chart(df):
    """
    Generate chart data for gender distribution
    
    Args:
        df: DataFrame of youth data
        
    Returns:
        JSON-serialized chart data
    """
    # Filter for active youth
    active_df = df[df['Employment Status'] == 'Active']
    
    # Count by gender
    gender_counts = active_df['Gender'].value_counts()
    
    # Format for chart display
    labels = gender_counts.index.tolist()
    values = gender_counts.values.tolist()
    
    # Generate colors
    colors = ['rgba(54, 162, 235, 0.7)', 'rgba(255, 99, 132, 0.7)']
    
    # Prepare chart data
    chart_data = {
        'labels': labels,
        'datasets': [{
            'label': 'Gender Distribution',
            'data': values,
            'backgroundColor': colors,
            'borderColor': colors,
            'borderWidth': 1
        }]
    }
    
    return json.dumps(chart_data)

def generate_race_chart(df):
    """
    Generate chart data for race distribution
    
    Args:
        df: DataFrame of youth data
        
    Returns:
        JSON-serialized chart data
    """
    # Filter for active youth
    active_df = df[df['Employment Status'] == 'Active']
    
    # Count by race
    race_counts = active_df['Race'].value_counts()
    
    # Format for chart display
    labels = race_counts.index.tolist()
    values = race_counts.values.tolist()
    
    # Generate colors (one for each race category)
    import random
    colors = []
    for i in range(len(labels)):
        r = random.randint(50, 200)
        g = random.randint(50, 200)
        b = random.randint(50, 200)
        colors.append(f'rgba({r}, {g}, {b}, 0.7)')
    
    # Prepare chart data
    chart_data = {
        'labels': labels,
        'datasets': [{
            'label': 'Race Distribution',
            'data': values,
            'backgroundColor': colors,
            'borderColor': colors,
            'borderWidth': 1
        }]
    }
    
    return json.dumps(chart_data)

def generate_job_title_chart(df):
    """
    Generate chart data for job title distribution
    
    Args:
        df: DataFrame of youth data
        
    Returns:
        JSON-serialized chart data
    """
    # Filter for active youth
    active_df = df[df['Employment Status'] == 'Active']
    
    # Count by job title
    job_title_counts = active_df['Job Title'].value_counts()
    
    # Format for chart display (top 10 job titles)
    job_title_counts = job_title_counts.head(10)
    labels = job_title_counts.index.tolist()
    values = job_title_counts.values.tolist()
    
    # Generate color gradient
    import matplotlib.cm as cm
    import matplotlib.colors as mcolors
    
    cmap = cm.get_cmap('Blues')
    colors = [mcolors.to_hex(cmap(i/len(labels))) for i in range(len(labels))]
    
    # Prepare chart data
    chart_data = {
        'labels': labels,
        'datasets': [{
            'label': 'Job Title Distribution',
            'data': values,
            'backgroundColor': colors,
            'borderColor': 'rgba(54, 162, 235, 1)',
            'borderWidth': 1
        }]
    }
    
    return json.dumps(chart_data)

def generate_site_type_chart(df):
    """
    Generate chart data for site type distribution
    
    Args:
        df: DataFrame of youth data
        
    Returns:
        JSON-serialized chart data
    """
    # Filter for active youth
    active_df = df[df['Employment Status'] == 'Active']
    
    # Count by site type
    site_type_counts = active_df['Site Type'].value_counts()
    
    # Format for chart display
    labels = site_type_counts.index.tolist()
    values = site_type_counts.values.tolist()
    
    # Generate colors
    colors = ['rgba(75, 192, 192, 0.7)', 'rgba(153, 102, 255, 0.7)', 
              'rgba(255, 159, 64, 0.7)', 'rgba(255, 205, 86, 0.7)',
              'rgba(54, 162, 235, 0.7)', 'rgba(201, 203, 207, 0.7)']
    
    # Extend colors if needed
    while len(colors) < len(labels):
        colors.extend(colors)
    
    # Truncate colors if needed
    colors = colors[:len(labels)]
    
    # Prepare chart data
    chart_data = {
        'labels': labels,
        'datasets': [{
            'label': 'Site Type Distribution',
            'data': values,
            'backgroundColor': colors,
            'borderColor': colors,
            'borderWidth': 1
        }]
    }
    
    return json.dumps(chart_data)

def generate_hiring_trend_chart(df):
    """
    Generate chart data for hiring trends over time
    
    Args:
        df: DataFrame of youth data
        
    Returns:
        JSON-serialized chart data
    """
    # Convert Start Date to datetime
    df['Start Date'] = pd.to_datetime(df['Start Date'], errors='coerce')
    
    # Group by month and count
    df['Start Month'] = df['Start Date'].dt.to_period('M')
    hiring_counts = df.groupby('Start Month').size().reset_index(name='count')
    
    # Convert period to string for JSON serialization
    hiring_counts['Start Month'] = hiring_counts['Start Month'].astype(str)
    
    # Sort by date
    hiring_counts = hiring_counts.sort_values('Start Month')
    
    # Get the most recent 24 months
    if len(hiring_counts) > 24:
        hiring_counts = hiring_counts.tail(24)
    
    # Format for chart display
    labels = hiring_counts['Start Month'].tolist()
    values = hiring_counts['count'].tolist()
    
    # Prepare chart data
    chart_data = {
        'labels': labels,
        'datasets': [{
            'label': 'New Hires',
            'data': values,
            'backgroundColor': 'rgba(54, 162, 235, 0.5)',
            'borderColor': 'rgba(54, 162, 235, 1)',
            'borderWidth': 1
        }]
    }
    
    return json.dumps(chart_data)

def generate_leaving_reasons_chart(df):
    """
    Generate chart data for reasons for leaving
    
    Args:
        df: DataFrame of youth data
        
    Returns:
        JSON-serialized chart data
    """
    # Filter for non-active youth that have a reason for leaving
    inactive_df = df[(df['Employment Status'] != 'Active') & (df['Reason for Leaving'].notna())]
    
    # Count by reason for leaving
    leaving_reasons = inactive_df['Reason for Leaving'].value_counts()
    
    # Format for chart display (top 10 reasons)
    leaving_reasons = leaving_reasons.head(10)
    labels = leaving_reasons.index.tolist()
    values = leaving_reasons.values.tolist()
    
    # Generate colors
    import matplotlib.cm as cm
    import matplotlib.colors as mcolors
    
    cmap = cm.get_cmap('Reds')
    colors = [mcolors.to_hex(cmap(i/len(labels))) for i in range(len(labels))]
    
    # Prepare chart data
    chart_data = {
        'labels': labels,
        'datasets': [{
            'label': 'Reasons for Leaving',
            'data': values,
            'backgroundColor': colors,
            'borderColor': 'rgba(255, 99, 132, 1)',
            'borderWidth': 1
        }]
    }
    
    return json.dumps(chart_data)

def generate_age_distribution_chart(df):
    """
    Generate chart data for age distribution
    
    Args:
        df: DataFrame of youth data
        
    Returns:
        JSON-serialized chart data
    """
    # Filter for active youth
    active_df = df[df['Employment Status'] == 'Active'].copy()
    
    # Ensure Age is numeric
    active_df['Age'] = pd.to_numeric(active_df['Age'], errors='coerce')
    
    # Create age bins using a different approach that avoids categorical issues
    bins = [15, 20, 25, 30, 35, 40, 45, 50, float('inf')]
    labels = ['15-19', '20-24', '25-29', '30-34', '35-39', '40-44', '45-49', '50+']
    
    # Create a function to assign age bins
    def assign_age_bin(age):
        if pd.isna(age):
            return "Unknown"
        for i, upper in enumerate(bins[1:]):
            if age < upper:
                return labels[i]
        return labels[-1]  # For any age >= the highest bin value
    
    # Apply the function to create the Age Bin column
    active_df['Age Bin'] = active_df['Age'].apply(assign_age_bin)
    
    # Count by age bin
    age_counts = active_df['Age Bin'].value_counts().reindex(labels)
    
    # Remove NaN values
    age_counts = age_counts.fillna(0).astype(int)
    
    # Format for chart display
    bin_labels = age_counts.index.tolist()
    values = age_counts.values.tolist()
    
    # Generate color gradient
    colors = [
        'rgba(54, 162, 235, 0.7)',
        'rgba(75, 192, 192, 0.7)',
        'rgba(153, 102, 255, 0.7)',
        'rgba(255, 159, 64, 0.7)',
        'rgba(255, 205, 86, 0.7)',
        'rgba(255, 99, 132, 0.7)',
        'rgba(201, 203, 207, 0.7)',
        'rgba(255, 99, 132, 0.7)'
    ]
    
    # Prepare chart data
    chart_data = {
        'labels': bin_labels,
        'datasets': [{
            'label': 'Age Distribution',
            'data': values,
            'backgroundColor': colors[:len(bin_labels)],
            'borderColor': colors[:len(bin_labels)],
            'borderWidth': 1
        }]
    }
    
    return json.dumps(chart_data)

def generate_employment_duration_chart(df):
    """
    Generate chart data for employment duration distribution (months active)
    
    Args:
        df: DataFrame of youth data
        
    Returns:
        JSON-serialized chart data
    """
    # Make a copy to avoid modifying the original
    df = df.copy()
    
    # Clean the data - ensure it's numeric
    df['Months Active'] = pd.to_numeric(df['Months Active'], errors='coerce')
    
    # Create duration bins using a manual approach to avoid categorical issues
    bins = [0, 3, 6, 12, 24, 36, 60, float('inf')]
    labels = ['0-3', '3-6', '6-12', '12-24', '24-36', '36-60', '60+']
    
    # Create a function to assign duration bins
    def assign_duration_bin(months):
        if pd.isna(months):
            return "Unknown"
        for i, upper in enumerate(bins[1:]):
            if months < upper:
                return labels[i]
        return labels[-1]  # For any duration >= the highest bin value
    
    # Apply the function to create the Duration Bin column
    df['Duration Bin'] = df['Months Active'].apply(assign_duration_bin)
    
    # Count by duration bin
    duration_counts = df['Duration Bin'].value_counts().reindex(labels)
    
    # Remove NaN values
    duration_counts = duration_counts.fillna(0).astype(int)
    
    # Format for chart display
    bin_labels = duration_counts.index.tolist()
    values = duration_counts.values.tolist()
    
    # Generate color gradient for each bin
    colors = []
    for i in range(len(bin_labels)):
        # Create a shade of green, darker for longer durations
        intensity = 80 + (i * 25)
        intensity = min(intensity, 220)  # Cap at 220 to keep it visible
        colors.append(f'rgba(75, {intensity}, 75, 0.7)')
    
    # Prepare chart data
    chart_data = {
        'labels': bin_labels,
        'datasets': [{
            'label': 'Employment Duration (Months)',
            'data': values,
            'backgroundColor': colors,
            'borderColor': 'rgba(75, 192, 192, 1)',
            'borderWidth': 1
        }]
    }
    
    return json.dumps(chart_data)

def generate_site_placement_table(df):
    """
    Generate data for site placement table
    
    Args:
        df: DataFrame of youth data
        
    Returns:
        List of site placement data with youth counts
    """
    # Filter for active youth
    active_df = df[df['Employment Status'] == 'Active']
    
    # Count by site placement and site type
    site_data = active_df.groupby(['Site Placement', 'Site Type']).size().reset_index(name='youth_count')
    
    # Sort by count (descending)
    site_data = site_data.sort_values('youth_count', ascending=False)
    
    # Convert to list of dictionaries
    result = []
    for _, row in site_data.iterrows():
        result.append({
            'site_name': row['Site Placement'],
            'site_type': row['Site Type'],
            'youth_count': row['youth_count']
        })
    
    return result

# Note: CSV preparation function removed as we now use Airtable API
# Data preparation is now handled in youth_airtable_service.py