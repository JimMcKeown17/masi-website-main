from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User

# Models & Forms
from .models import MentorVisit, School
from .forms import MentorVisitForm

# Services
from .services.airtable_service import fetch_airtable_records
from .services.data_processing import process_airtable_records, get_active_records, count_job_titles

# Visualizations
from .visualizations.charts import create_job_title_chart
from .visualizations.mentor_charts import (
    generate_visit_frequency_chart,
    generate_quality_rating_chart,
    generate_tracker_accuracy_chart,
    generate_school_visit_map,
    generate_dashboard_summary
)

def dashboard_main(request):
    """Main dashboard view with Airtable data"""
    # Fetch data from Airtable
    records, error = fetch_airtable_records()
    
    if error:
        return render(request, 'dashboards/dashboard_main.html', {
            'error_message': error,
            'troubleshooting_tips': [
                "Check your .env file is properly formatted",
                "Verify Django is loading your .env file correctly",
                "Make sure the variable names match exactly"
            ]
        })
    
    # Process the records
    df = process_airtable_records(records)
    
    # Check if DataFrame was created successfully
    if df is None or df.empty:
        return render(request, 'dashboards/dashboard_main.html', {
            'error_message': 'No records found or error processing the data'
        })
    
    # Diagnostic print statements
    print("DataFrame Columns:", list(df.columns))
    print("\nFirst few records:")
    print(df.head())
    
    # Filter for active records
    active_df = get_active_records(df)
    
    # If no active records found
    if active_df is None or active_df.empty:
        return render(request, 'dashboards/dashboard_main.html', {
            'error_message': 'No active records found. Check your Employment Status column.',
            'diagnostic_info': {
                'columns': list(df.columns),
                'total_records': len(df),
                'status_values': df['Employment Status'].unique().tolist() if 'Employment Status' in df.columns else []
            }
        })
    
    # Count job titles for active records
    job_title_counts = count_job_titles(active_df)
    
    if job_title_counts is None:
        return render(request, 'dashboards/dashboard_main.html', {
            'error_message': 'Job Title column not found in data',
            'diagnostic_info': {
                'columns': list(active_df.columns),
                'total_records': len(active_df)
            }
        })
    
    # Create visualization
    plot_html = create_job_title_chart(job_title_counts)
    
    # Prepare context to pass to template
    context = {
        'job_title_plot': plot_html,
        'job_title_counts': job_title_counts.to_dict(),
        'total_active_records': len(active_df),
        'total_records': len(df)
    }
    
    return render(request, 'dashboards/dashboard_main.html', context)

@login_required
def mentor_visit_form(request):
    """View for creating a new mentor visit report"""
    if request.method == 'POST':
        form = MentorVisitForm(request.POST)
        if form.is_valid():
            visit = form.save(commit=False)
            visit.mentor = request.user
            visit.save()
            messages.success(request, 'Visit report submitted successfully!')
            return redirect('mentor_dashboard')
    else:
        form = MentorVisitForm()
    
    return render(request, 'dashboards/mentor_visits.html', {
        'form': form,
        'title': 'Submit School Visit Report'
    })

# Update the mentor_dashboard function in your views.py file

@login_required
def mentor_dashboard(request):
    """Main dashboard view for mentor visits"""
    # Get filter parameters
    time_filter = request.GET.get('time_filter', 'all')
    school_filter = request.GET.get('school', '')
    mentor_filter = request.GET.get('mentor', '')
    
    # Base queryset
    visits = MentorVisit.objects.all()
    
    # Apply time filter
    if time_filter == '30days':
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        visits = visits.filter(visit_date__gte=thirty_days_ago)
    elif time_filter == '90days':
        ninety_days_ago = timezone.now().date() - timedelta(days=90)
        visits = visits.filter(visit_date__gte=ninety_days_ago)
    elif time_filter == 'thisyear':
        year_start = timezone.now().date().replace(month=1, day=1)
        visits = visits.filter(visit_date__gte=year_start)
    
    # Apply school filter
    if school_filter:
        visits = visits.filter(school_id=school_filter)
    
    # Apply mentor filter
    if mentor_filter:
        visits = visits.filter(mentor_id=mentor_filter)
    
    # Get all schools for the filter dropdown
    schools = School.objects.filter(is_active=True).order_by('name')
    
    # Get all mentors for the filter dropdown
    mentors = User.objects.filter(visits__isnull=False).distinct().order_by('first_name', 'last_name')
    
    # Generate chart data
    time_period = 'week' if time_filter in ['30days', '90days'] else 'month'
    
    # Get all visits (unfiltered by time) for schools last visited component
    all_visits = MentorVisit.objects.all()
    if school_filter:
        all_visits = all_visits.filter(school_id=school_filter)
    if mentor_filter:
        all_visits = all_visits.filter(mentor_id=mentor_filter)
    
    # Generate schools last visited data
    from .visualizations.mentor_charts import generate_schools_last_visited
    schools_last_visited = generate_schools_last_visited(all_visits)
    
    context = {
        'schools': schools,
        'mentors': mentors,
        'selected_time_filter': time_filter,
        'selected_school': school_filter,
        'selected_mentor': mentor_filter,
        'visit_frequency_chart': generate_visit_frequency_chart(visits, time_period),
        'quality_rating_chart': generate_quality_rating_chart(visits),
        'tracker_accuracy_chart': generate_tracker_accuracy_chart(visits),
        'school_visit_map': generate_school_visit_map(visits),
        'summary': generate_dashboard_summary(visits),
        'schools_last_visited': schools_last_visited,  # Add the new data
        'title': 'Mentor Visit Dashboard'
    }
    
    return render(request, 'dashboards/mentor_dashboard.html', context)