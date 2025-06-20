from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
import pandas as pd
import os
from django.conf import settings
import json
from django.db.models import Avg, Count
from zoneinfo import ZoneInfo
from django.http import JsonResponse
from .forms import MentorVisitForm, YeboVisitForm, ThousandStoriesVisitForm

# Models & Forms - Update these imports
from api.models import MentorVisit, School, YeboVisit, ThousandStoriesVisit, WELA_assessments

# Airtable Services
from .services.airtable_service import fetch_youth_airtable_records
from .services.airtable_service import process_youth_airtable_records
from .services.data_processing import get_active_records, count_job_titles

# Mentor Dashboard Visualizations
from .visualizations.charts import create_job_title_chart
from .visualizations.mentor_charts import (
    generate_combined_visit_frequency_chart,
    generate_visit_frequency_chart,
    generate_combined_quality_rating_chart,
    generate_quality_rating_chart,
    generate_yebo_quality_rating_chart,
    generate_thousand_stories_quality_rating_chart,
    generate_letter_tracker_accuracy_chart,
    generate_tracker_accuracy_chart,
    generate_combined_school_visit_map,
    generate_school_visit_map,
    generate_yebo_school_visit_map,
    generate_thousand_stories_school_visit_map,
    generate_combined_dashboard_summary,
    generate_dashboard_summary,
    get_recent_literacy_submissions,
    get_recent_yebo_submissions,
    get_recent_thousand_stories_submissions
)

# Youth Dashboard Visualizations
from .visualizations.youth_charts import (
    ensure_string_values,
    generate_youth_summary,
    generate_gender_chart,
    generate_race_chart,
    generate_job_title_chart,
    generate_site_type_chart,
    generate_hiring_trend_chart,
    generate_leaving_reasons_chart,
    generate_age_distribution_chart,
    generate_employment_duration_chart,
    generate_site_placement_table
)

from dashboards.visualizations.assessment_charts import AssessmentCharts

def dashboard_main(request):
    """
    Main dashboard hub page showing links to all available dashboards
    """
    # Initialize stats dictionaries
    mentor_stats = {
        'total_visits': 0,
        'recent_visits': 0,
        'schools_visited': 0,
        'avg_quality': 0
    }
    
    youth_stats = {}
    
    # Add literacy stats that the template is looking for
    literacy_stats = {
        'total_visits': 0,
        'recent_visits': 0,
        'schools_visited': 0,
        'avg_quality': 0
    }
    
    # Try to get mentor stats if available
    try:
        from .visualizations.mentor_charts import generate_dashboard_summary
        from api.models import MentorVisit
        
        # Get all mentor visits
        visits = MentorVisit.objects.all()
        
        # Generate summary stats
        if visits.exists():
            mentor_stats = generate_dashboard_summary(visits)
    except Exception as e:
        # If there's an error, we'll just use the default values in the template
        import logging
        logging.error(f"Error fetching mentor stats: {str(e)}")
    
    # Try to get youth stats if available
    try:
        from .services.airtable_service import fetch_youth_airtable_records, process_youth_airtable_records
        from .visualizations.youth_charts import generate_youth_summary
        
        # Fetch youth data from Airtable
        records, error = fetch_youth_airtable_records()
        
        if not error and records:
            # Process the records
            youth_df = process_youth_airtable_records(records)
            
            # Generate summary stats
            if not youth_df.empty:
                youth_stats = generate_youth_summary(youth_df)
    except Exception as e:
        # If there's an error, we'll just use the default values in the template
        import logging
        logging.error(f"Error fetching youth stats: {str(e)}")
    
    context = {
        'mentor_stats': mentor_stats,
        'youth_stats': youth_stats,
        'literacy_stats': literacy_stats,  # Add the missing literacy_stats
        'title': 'Dashboards'
    }
    
    return render(request, 'dashboards/dashboard_main.html', context)

@login_required
def mentor_visit_form(request):
    """View for creating a new mentor visit report"""
    form_type = request.GET.get('type', 'masi_literacy')  # Default to Masi Literacy
    
    if request.method == 'POST':
        form_type = request.POST.get('form_type', 'masi_literacy')
        
        if form_type == 'yebo':
            form = YeboVisitForm(request.POST)
            if form.is_valid():
                visit = form.save(commit=False)
                visit.mentor = request.user
                visit.save()
                messages.success(request, 'Yebo visit report submitted successfully!')
                return redirect('mentor_dashboard')
        elif form_type == '1000_stories':
            form = ThousandStoriesVisitForm(request.POST)
            if form.is_valid():
                visit = form.save(commit=False)
                visit.mentor = request.user
                visit.save()
                messages.success(request, '1000 Stories visit report submitted successfully!')
                return redirect('mentor_dashboard')
        else:  # Default to masi_literacy
            form = MentorVisitForm(request.POST)
            if form.is_valid():
                visit = form.save(commit=False)
                visit.mentor = request.user
                visit.save()
                messages.success(request, 'Masi Literacy visit report submitted successfully!')
                return redirect('mentor_dashboard')
    else:
        if form_type == 'yebo':
            form = YeboVisitForm()
        elif form_type == '1000_stories':
            form = ThousandStoriesVisitForm()
        else:  # Default to masi_literacy
            form = MentorVisitForm()
    
    return render(request, 'dashboards/mentor_visits.html', {
        'form': form,
        'form_type': form_type,
        'title': 'Submit School Visit Report'
    })

@login_required
def mentor_dashboard(request):
    """Main dashboard view for mentor visits - updated to handle all three visit types"""
    try:
        # Get filter parameters
        time_filter = request.GET.get('time_filter', 'all')
        school_filter = request.GET.get('school', '')
        mentor_filter = request.GET.get('mentor', '')
        
        # Base querysets for all three visit types
        mentor_visits = MentorVisit.objects.all()
        yebo_visits = YeboVisit.objects.all()
        thousand_stories_visits = ThousandStoriesVisit.objects.all()
        
        # Apply time filter to all visit types
        if time_filter == '7days':
            seven_days_ago = timezone.now().date() - timedelta(days=7)
            mentor_visits = mentor_visits.filter(visit_date__gte=seven_days_ago)
            yebo_visits = yebo_visits.filter(visit_date__gte=seven_days_ago)
            thousand_stories_visits = thousand_stories_visits.filter(visit_date__gte=seven_days_ago)
        elif time_filter == '30days':
            thirty_days_ago = timezone.now().date() - timedelta(days=30)
            mentor_visits = mentor_visits.filter(visit_date__gte=thirty_days_ago)
            yebo_visits = yebo_visits.filter(visit_date__gte=thirty_days_ago)
            thousand_stories_visits = thousand_stories_visits.filter(visit_date__gte=thirty_days_ago)
        elif time_filter == '90days':
            ninety_days_ago = timezone.now().date() - timedelta(days=90)
            mentor_visits = mentor_visits.filter(visit_date__gte=ninety_days_ago)
            yebo_visits = yebo_visits.filter(visit_date__gte=ninety_days_ago)
            thousand_stories_visits = thousand_stories_visits.filter(visit_date__gte=ninety_days_ago)
        elif time_filter == 'thisyear':
            year_start = timezone.now().date().replace(month=1, day=1)
            mentor_visits = mentor_visits.filter(visit_date__gte=year_start)
            yebo_visits = yebo_visits.filter(visit_date__gte=year_start)
            thousand_stories_visits = thousand_stories_visits.filter(visit_date__gte=year_start)
        
        # Apply school filter to all visit types
        if school_filter:
            mentor_visits = mentor_visits.filter(school_id=school_filter)
            yebo_visits = yebo_visits.filter(school_id=school_filter)
            thousand_stories_visits = thousand_stories_visits.filter(school_id=school_filter)
        
        # Apply mentor filter to all visit types
        if mentor_filter:
            mentor_visits = mentor_visits.filter(mentor_id=mentor_filter)
            yebo_visits = yebo_visits.filter(mentor_id=mentor_filter)
            thousand_stories_visits = thousand_stories_visits.filter(mentor_id=mentor_filter)
        
        # Get all schools for the filter dropdown
        schools = School.objects.filter(is_active=True).order_by('name')
        
        # Get all mentors for the filter dropdown (mentors who have submitted any type of visit)
        mentor_ids = set()
        mentor_ids.update(MentorVisit.objects.values_list('mentor_id', flat=True))
        mentor_ids.update(YeboVisit.objects.values_list('mentor_id', flat=True))
        mentor_ids.update(ThousandStoriesVisit.objects.values_list('mentor_id', flat=True))
        mentors = User.objects.filter(id__in=mentor_ids).distinct().order_by('first_name', 'last_name')
        
        # Generate chart data
        time_period = 'week' if time_filter in ['7days', '30days', '90days'] else 'month'
        
        # Get all visits (unfiltered by time) for schools last visited component
        all_mentor_visits = MentorVisit.objects.all()
        if school_filter:
            all_mentor_visits = all_mentor_visits.filter(school_id=school_filter)
        if mentor_filter:
            all_mentor_visits = all_mentor_visits.filter(mentor_id=mentor_filter)
        
        # Generate schools last visited data (using literacy visits for now)
        from .visualizations.mentor_charts import generate_schools_last_visited
        schools_last_visited = generate_schools_last_visited(all_mentor_visits)
        
        # Get recent submissions for each visit type
        recent_literacy_submissions = get_recent_literacy_submissions(mentor_visits, 50)
        recent_yebo_submissions = get_recent_yebo_submissions(yebo_visits, 50)
        recent_stories_submissions = get_recent_thousand_stories_submissions(thousand_stories_visits, 50)
        
        context = {
            'schools': schools,
            'mentors': mentors,
            'selected_time_filter': time_filter,
            'selected_school': school_filter,
            'selected_mentor': mentor_filter,
            
            # Combined charts showing all visit types
            'combined_visit_frequency_chart': generate_combined_visit_frequency_chart(mentor_visits, yebo_visits, thousand_stories_visits, time_period),
            'combined_quality_rating_chart': generate_combined_quality_rating_chart(mentor_visits, yebo_visits, thousand_stories_visits),
            'combined_school_visit_map': generate_combined_school_visit_map(mentor_visits, yebo_visits, thousand_stories_visits),
            'combined_summary': generate_combined_dashboard_summary(mentor_visits, yebo_visits, thousand_stories_visits),
            
            # Literacy-specific charts
            'literacy_visit_frequency_chart': generate_visit_frequency_chart(mentor_visits, time_period),
            'literacy_quality_rating_chart': generate_quality_rating_chart(mentor_visits),
            'letter_tracker_accuracy_chart': generate_letter_tracker_accuracy_chart(mentor_visits),
            'literacy_school_visit_map': generate_school_visit_map(mentor_visits),
            'literacy_summary': generate_dashboard_summary(mentor_visits),
            
            # Yebo-specific charts
            'yebo_visit_frequency_chart': generate_visit_frequency_chart(yebo_visits, time_period),
            'yebo_quality_rating_chart': generate_yebo_quality_rating_chart(yebo_visits),
            'yebo_school_visit_map': generate_yebo_school_visit_map(yebo_visits),
            
            # 1000 Stories-specific charts  
            'stories_visit_frequency_chart': generate_visit_frequency_chart(thousand_stories_visits, time_period),
            'stories_quality_rating_chart': generate_thousand_stories_quality_rating_chart(thousand_stories_visits),
            'stories_school_visit_map': generate_thousand_stories_school_visit_map(thousand_stories_visits),
            
            # Recent submissions for each type
            'recent_literacy_submissions': recent_literacy_submissions,
            'recent_yebo_submissions': recent_yebo_submissions,
            'recent_stories_submissions': recent_stories_submissions,
            
            'schools_last_visited': schools_last_visited,
            'title': 'Mentor Visit Dashboard'
        }
        
        return render(request, 'dashboards/mentor_dashboard.html', context)
    
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        
        # Log the full exception traceback
        logger.error(f"MENTOR DASHBOARD ERROR: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return a more informative error page
        return render(request, 'dashboards/dashboard_main.html', {
            'error_message': f"Error: {str(e)}",
            'traceback': traceback.format_exc(),
            'title': 'Error in Mentor Dashboard'
        })

@login_required
def youth_dashboard(request):
    """
    Dashboard view for youth data visualization using Airtable API
    """
    try:
        # Fetch data from Airtable
        records, error = fetch_youth_airtable_records()
        
        if error:
            return render(request, 'dashboards/youth_dashboard.html', {
                'error_message': error,
                'troubleshooting_tips': [
                    "Check your environment variables are properly set",
                    "Verify that AIRTABLE_API_KEY, AIRTABLE_BASE_ID, and AIRTABLE_COMBINED_YOUTH_DATA_TABLE_ID are correctly configured",
                    "Make sure your Airtable API key has access to the base containing the youth data"
                ],
                'title': 'Youth Dashboard'
            })
        
        # Process the records
        youth_df = process_youth_airtable_records(records)
        
        # Check if DataFrame was created successfully
        if youth_df is None or youth_df.empty:
            return render(request, 'dashboards/youth_dashboard.html', {
                'error_message': 'No records found or error processing the data',
                'title': 'Youth Dashboard'
            })
        
        # Apply filters from GET parameters
        employment_status = request.GET.get('employment_status', 'Active')
        site_type = request.GET.get('site_type', '')
        job_title = request.GET.get('job_title', '')
        
        # Create a filtered dataframe for charts that need it
        filtered_df = youth_df.copy()
        
        if employment_status and employment_status != 'All':
            filtered_df = filtered_df[filtered_df['Employment Status'] == employment_status]
        
        if site_type:
            filtered_df = filtered_df[filtered_df['Site Type'] == site_type]
            
        if job_title:
            filtered_df = filtered_df[filtered_df['Job Title'] == job_title]
        
        # Safely ensure string values for filtering columns
        youth_df = ensure_string_values(youth_df, 'Employment Status')
        youth_df = ensure_string_values(youth_df, 'Site Type')
        youth_df = ensure_string_values(youth_df, 'Job Title')
        
        # Get unique values for filter dropdowns
        status_options = youth_df['Employment Status'].dropna().unique().tolist()
        site_type_options = youth_df['Site Type'].dropna().unique().tolist()
        job_title_options = youth_df['Job Title'].dropna().unique().tolist()
        
        # Generate all chart data
        context = {
            'title': 'Youth Dashboard',
            'summary': generate_youth_summary(youth_df),
            'gender_chart': generate_gender_chart(filtered_df),
            'race_chart': generate_race_chart(filtered_df),
            'job_title_chart': generate_job_title_chart(filtered_df),
            'site_type_chart': generate_site_type_chart(filtered_df),
            'hiring_trend_chart': generate_hiring_trend_chart(youth_df),  # All youth for hiring trends
            'leaving_reasons_chart': generate_leaving_reasons_chart(youth_df),  # All youth for leaving reasons
            'age_distribution_chart': generate_age_distribution_chart(filtered_df),
            'employment_duration_chart': generate_employment_duration_chart(youth_df),  # All youth for duration
            'site_placement_table': generate_site_placement_table(filtered_df),
            
            # Filter options and selected values
            'status_options': status_options,
            'site_type_options': site_type_options,
            'job_title_options': job_title_options,
            'selected_status': employment_status,
            'selected_site_type': site_type,
            'selected_job_title': job_title
        }
        
        return render(request, 'dashboards/youth_dashboard.html', context)
        
    except Exception as e:
        # Log the error and return a friendly message
        import traceback
        traceback_str = traceback.format_exc()
        
        return render(request, 'dashboards/youth_dashboard.html', {
            'error_message': f'Error processing data: {str(e)}',
            'traceback': traceback_str,
            'title': 'Youth Dashboard'
        })
        
@login_required
def airtable_debug(request):
    """
    Debug view for examining Airtable data structure
    """
    # Only accessible in debug mode
    from django.conf import settings
    if not settings.DEBUG:
        return JsonResponse({"error": "Debug view only available in DEBUG mode"}, status=403)
    
    # Fetch raw data from Airtable
    records, error = fetch_youth_airtable_records()
    
    if error:
        return JsonResponse({"error": error}, status=500)
    
    # Process a sample record to examine structure
    if records and len(records) > 0:
        # Get first record
        first_record = records[0]
        
        # Find fields with list values
        list_fields = {}
        for key, value in first_record.get('fields', {}).items():
            if isinstance(value, list):
                list_fields[key] = value
        
        # Count record and field types
        record_count = len(records)
        field_types = {}
        
        # Sample up to 10 records
        sample_size = min(10, record_count)
        sample_records = records[:sample_size]
        
        # Examine each field in the sample records
        all_fields = set()
        for record in sample_records:
            fields = record.get('fields', {})
            all_fields.update(fields.keys())
        
        # Count the types of values in each field
        for field in all_fields:
            field_types[field] = {
                "types": {},
                "null_count": 0,
                "list_count": 0,
                "sample_values": []
            }
            
            # Check each record for this field
            for record in sample_records:
                value = record.get('fields', {}).get(field)
                
                # Track type and null values
                if value is None:
                    field_types[field]["null_count"] += 1
                else:
                    value_type = type(value).__name__
                    field_types[field]["types"][value_type] = field_types[field]["types"].get(value_type, 0) + 1
                    
                    # Track list fields
                    if isinstance(value, list):
                        field_types[field]["list_count"] += 1
                    
                    # Add sample value if we have fewer than 3
                    if len(field_types[field]["sample_values"]) < 3:
                        sample_value = str(value)
                        if len(sample_value) > 100:
                            sample_value = sample_value[:100] + "..."
                        field_types[field]["sample_values"].append(sample_value)
        
        return JsonResponse({
            "record_count": record_count,
            "fields_with_list_values": list_fields,
            "field_analysis": field_types,
            "sample_record": first_record
        }, json_dumps_params={'indent': 2})
    
    return JsonResponse({"message": "No records found"}, status=404)

@login_required
def literacy_management_dashboard(request):
    """Dashboard for literacy management data"""
    try:            
        # Get time period filter
        time_period = request.GET.get('time_period', 'all')
        
        # Get current date and calculate filter dates
        today = timezone.now()
        filter_start_date = None
        
        if time_period == '7days':
            filter_start_date = today - timedelta(days=7)
        elif time_period == '30days':
            filter_start_date = today - timedelta(days=30)
        elif time_period == '90days':
            filter_start_date = today - timedelta(days=90)
        elif time_period == 'thisyear':
            filter_start_date = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Base queryset - get ALL visits first for calculating recent_visits
        all_visits = MentorVisit.objects.all()
        
        # Filtered queryset based on time period
        visits_queryset = all_visits
        if filter_start_date:
            visits_queryset = visits_queryset.filter(visit_date__gte=filter_start_date)
        
        # Calculate basic stats
        total_visits = visits_queryset.count()
        recent_visits = all_visits.filter(visit_date__gte=today - timedelta(days=30)).count()  # Always use all_visits for this calculation
        
        # For time_period='30days', recent_visits and total_visits should be the same
        if time_period == '30days':
            recent_visits = total_visits
            
        schools_visited = School.objects.filter(visits__in=visits_queryset).distinct().count()
        avg_quality = visits_queryset.aggregate(Avg('quality_rating'))['quality_rating__avg'] or 0
        
        # Get all mentors
        mentors = User.objects.filter(visits__isnull=False).distinct()
        
        # Calculate visits by mentor over time
        time_periods = []
        mentor_visits_data = []
        
        # Calculate time periods starting from the most recent month
        current_month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Adjust number of months to show based on time period
        if time_period == '7days':
            num_months = 1
        elif time_period == '30days':
            num_months = 1
        elif time_period == '90days':
            num_months = 3
        elif time_period == 'thisyear':
            num_months = current_month_start.month
        else:
            num_months = 4  # Default to showing last 4 months
        
        for i in range(num_months):
            month_start = current_month_start - timedelta(days=30 * i)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            time_periods.insert(0, month_start.strftime('%B %Y'))
        
        # Create dataset for each mentor
        for mentor in mentors:
            mentor_data = {
                'label': f"{mentor.first_name} {mentor.last_name}",
                'data': [],
                'backgroundColor': f'rgba({hash(mentor.username) % 255}, {(hash(mentor.username) >> 8) % 255}, {(hash(mentor.username) >> 16) % 255}, 0.8)'
            }
            
            for i in range(num_months):
                month_start = current_month_start - timedelta(days=30 * i)
                month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                visits = visits_queryset.filter(
                    mentor=mentor,
                    visit_date__gte=month_start,
                    visit_date__lte=month_end
                ).count()
                mentor_data['data'].insert(0, visits)
            
            mentor_visits_data.append(mentor_data)
        
        # Calculate quality ratings by mentor
        mentor_names = []
        quality_ratings = []
        
        for mentor in mentors:
            mentor_names.append(f"{mentor.first_name} {mentor.last_name}")
            avg_rating = visits_queryset.filter(mentor=mentor).aggregate(
                Avg('quality_rating')
            )['quality_rating__avg'] or 0
            quality_ratings.append(round(avg_rating, 2))
        
        # Calculate cumulative visits by mentor
        cumulative_data = []
        
        for mentor in mentors:
            # Get all visits for this mentor ordered by date
            mentor_visits = visits_queryset.filter(mentor=mentor).order_by('visit_date')
            cumulative_count = 0
            data_points = []
            
            # Calculate cumulative visits over time
            for visit in mentor_visits:
                cumulative_count += 1
                data_points.append({
                    'x': visit.visit_date.strftime('%Y-%m-%d'),
                    'y': cumulative_count
                })
            
            # Only add mentors who have visits
            if data_points:
                cumulative_data.append({
                    'label': f"{mentor.first_name} {mentor.last_name}",
                    'data': data_points,
                    'borderColor': f'rgba({hash(mentor.username) % 255}, {(hash(mentor.username) >> 8) % 255}, {(hash(mentor.username) >> 16) % 255}, 1)',
                    'backgroundColor': f'rgba({hash(mentor.username) % 255}, {(hash(mentor.username) >> 8) % 255}, {(hash(mentor.username) >> 16) % 255}, 1)',
                    'borderWidth': 2,
                    'tension': 0.4,
                    'fill': False
                })
        
        # Get schools not visited in last 30 days
        schools_not_visited = []
        for school in School.objects.all():
            last_visit = visits_queryset.filter(school=school).order_by('-visit_date').first()
            
            if not last_visit or (today.date() - last_visit.visit_date).days > 30:
                schools_not_visited.append({
                    'name': school.name,
                    'last_visited_by': f"{last_visit.mentor.first_name} {last_visit.mentor.last_name}" if last_visit else 'Never',
                    'days_since_visit': (today.date() - last_visit.visit_date).days if last_visit else 999
                })
        
        # Sort schools by days since last visit
        schools_not_visited.sort(key=lambda x: x['days_since_visit'], reverse=True)
        
        # Calculate average visits per week per mentor
        mentor_weekly_stats = []
        for mentor in mentors:
            mentor_visits = visits_queryset.filter(mentor=mentor)
            total_visits = mentor_visits.count()
            
            if total_visits > 0:
                first_visit = mentor_visits.order_by('visit_date').first()
                weeks_active = max(1, (today.date() - first_visit.visit_date).days / 7)  # At least 1 week
                avg_visits_per_week = round(total_visits / weeks_active, 1)
                
                mentor_weekly_stats.append({
                    'name': f"{mentor.first_name} {mentor.last_name}",
                    'total_visits': total_visits,
                    'avg_visits_per_week': avg_visits_per_week,
                    'start_date': first_visit.visit_date.strftime('%B %d, %Y'),
                    'weeks_active': round(weeks_active, 1)
                })
        
        # Sort by average visits per week in descending order
        mentor_weekly_stats.sort(key=lambda x: x['avg_visits_per_week'], reverse=True)
        
        context = {
            'total_visits': total_visits,
            'visits_last_30_days': recent_visits,
            'schools_visited': schools_visited,
            'avg_quality_rating': round(avg_quality, 1),
            'time_periods': json.dumps(time_periods),
            'mentor_visits_data': json.dumps(mentor_visits_data),
            'mentor_names': json.dumps(mentor_names),
            'quality_ratings': json.dumps(quality_ratings),
            'schools_not_visited': schools_not_visited,
            'cumulative_visits_data': json.dumps(cumulative_data),
            'selected_time_period': time_period,
            'mentor_weekly_stats': mentor_weekly_stats
        }
        
        return render(request, 'dashboards/literacy_management_dashboard.html', context)

    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        
        # Log the full exception traceback
        logger.error(f"LITERACY VIEW ERROR: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return a more informative error page
        return render(request, 'dashboards/dashboard_main.html', {
            'error_message': f"Error: {str(e)}",
            'traceback': traceback.format_exc(),
            'title': 'Error in Literacy Dashboard'
        })

def database_check(request):
    """Temporary diagnostic view"""
    from django.db import connection
    import json
    from django.http import JsonResponse
    
    # Only allow superusers for security
    if not request.user.is_superuser:
        return JsonResponse({"error": "Not authorized"}, status=403)
    
    # Check tables
    with connection.cursor() as cursor:
        # List all tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        # Check if our tables exist
        dashboards_school_exists = 'dashboards_school' in tables
        api_school_exists = 'api_school' in tables
        dashboards_mentorvisit_exists = 'dashboards_mentorvisit' in tables
        api_mentorvisit_exists = 'api_mentorvisit' in tables
        
        # Count records in key tables
        counts = {}
        for table in ['dashboards_school', 'api_school', 'dashboards_mentorvisit', 'api_mentorvisit']:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cursor.fetchone()[0]
            except:
                counts[table] = "Table doesn't exist"
    
    return JsonResponse({
        "all_tables": tables,
        "dashboards_school_exists": dashboards_school_exists,
        "api_school_exists": api_school_exists,
        "dashboards_mentorvisit_exists": dashboards_mentorvisit_exists,
        "api_mentorvisit_exists": api_mentorvisit_exists,
        "record_counts": counts
    })

def debug_check(request):
    """Ultra-simple diagnostic view"""
    from django.http import HttpResponse
    import sys
    import os
    
    debug_info = [
        f"Python version: {sys.version}",
        f"Environment: {os.environ.get('ENVIRONMENT', 'Not set')}",
        f"Database URL: {os.environ.get('DATABASE_URL', '[REDACTED]')[:10]}...",
    ]
    
    # Check tables directly
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            tables = [row[0] for row in cursor.fetchall()]
            debug_info.append(f"Tables: {', '.join(tables)}")
            
            # Check specific tables
            for table in ['dashboards_school', 'dashboards_mentorvisit', 'api_school', 'api_mentorvisit']:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    debug_info.append(f"Table {table}: {count} rows")
                except Exception as e:
                    debug_info.append(f"Table {table}: Error - {str(e)}")
    except Exception as e:
        debug_info.append(f"Database error: {str(e)}")
    
    return HttpResponse("<br>".join(debug_info), content_type="text/plain")

@login_required
def assessment_dashboard(request):
    """Main assessment dashboard view"""
    
    # Get filter parameters
    year = request.GET.get('year')
    school = request.GET.get('school')
    grade = request.GET.get('grade')
    
    # Convert year to int if provided
    if year:
        try:
            year = int(year)
        except ValueError:
            year = None
    
    # Get summary statistics
    stats = AssessmentCharts.get_summary_stats(year=year)
    
    # Get available filter options
    available_years = WELA_assessments.objects.values_list('assessment_year', flat=True).distinct().order_by('-assessment_year')
    available_schools = WELA_assessments.objects.values_list('school', flat=True).distinct().order_by('school')
    available_grades = WELA_assessments.objects.values_list('grade', flat=True).distinct().order_by('grade')
    
    # Generate charts
    progress_chart = AssessmentCharts.get_progress_over_time_chart(year=year, school=school, grade=grade)
    school_comparison_chart = AssessmentCharts.get_school_comparison_chart(year=year)
    skill_breakdown_chart = AssessmentCharts.get_skill_breakdown_chart(year=year, period='nov')
    grade_performance_chart = AssessmentCharts.get_grade_performance_chart(year=year)
    
    context = {
        'stats': stats,
        'progress_chart': progress_chart,
        'school_comparison_chart': school_comparison_chart,
        'skill_breakdown_chart': skill_breakdown_chart,
        'grade_performance_chart': grade_performance_chart,
        'available_years': available_years,
        'available_schools': available_schools,
        'available_grades': available_grades,
        'selected_year': year,
        'selected_school': school,
        'selected_grade': grade,
    }
    
    return render(request, 'dashboards/assessment_dashboard.html', context)

@login_required
def assessment_data_api(request):
    """API endpoint for dynamic chart updates"""
    
    year = request.GET.get('year')
    school = request.GET.get('school')
    grade = request.GET.get('grade')
    chart_type = request.GET.get('chart_type')
    
    if year:
        try:
            year = int(year)
        except ValueError:
            year = None
    
    if chart_type == 'progress':
        chart_html = AssessmentCharts.get_progress_over_time_chart(year=year, school=school, grade=grade)
    elif chart_type == 'schools':
        chart_html = AssessmentCharts.get_school_comparison_chart(year=year)
    elif chart_type == 'skills':
        period = request.GET.get('period', 'nov')
        chart_html = AssessmentCharts.get_skill_breakdown_chart(year=year, period=period)
    elif chart_type == 'grades':
        chart_html = AssessmentCharts.get_grade_performance_chart(year=year)
    else:
        return JsonResponse({'error': 'Invalid chart type'}, status=400)
    
    return JsonResponse({'chart_html': chart_html})

@login_required
def student_detail_view(request, mcode):
    """Detailed view for individual student progress"""
    
    try:
        # Get all assessment records for this student
        student_assessments = WELA_assessments.objects.filter(mcode=mcode).order_by('assessment_year')
        
        if not student_assessments.exists():
            return render(request, 'dashboards/student_not_found.html', {'mcode': mcode})
        
        # Get the latest record for basic info
        latest_assessment = student_assessments.last()
        
        # Prepare data for individual student progress chart
        years = []
        jan_scores = []
        june_scores = []
        nov_scores = []
        
        for assessment in student_assessments:
            years.append(assessment.assessment_year)
            jan_scores.append(assessment.jan_total or 0)
            june_scores.append(assessment.june_total or 0)
            nov_scores.append(assessment.nov_total or 0)
        
        # Create individual progress chart
        import plotly.graph_objects as go
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=years,
            y=jan_scores,
            mode='lines+markers',
            name='January',
            line=dict(color='#F18F01', width=2),
            marker=dict(size=8)
        ))
        
        fig.add_trace(go.Scatter(
            x=years,
            y=june_scores,
            mode='lines+markers',
            name='June',
            line=dict(color='#C73E1D', width=2),
            marker=dict(size=8)
        ))
        
        fig.add_trace(go.Scatter(
            x=years,
            y=nov_scores,
            mode='lines+markers',
            name='November',
            line=dict(color='#2E86AB', width=2),
            marker=dict(size=8)
        ))
        
        fig.update_layout(
            title=f'Individual Progress: {latest_assessment.full_name}',
            xaxis_title='Year',
            yaxis_title='Total Score',
            template='plotly_white',
            height=400
        )
        
        individual_chart = fig.to_html(include_plotlyjs=True)
        
        context = {
            'student': latest_assessment,
            'assessments': student_assessments,
            'individual_chart': individual_chart,
        }
        
        return render(request, 'dashboards/student_detail.html', context)
        
    except Exception as e:
        return render(request, 'dashboards/error.html', {'error': str(e)})