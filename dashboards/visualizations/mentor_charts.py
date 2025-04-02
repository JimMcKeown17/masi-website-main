import json
from datetime import datetime, timedelta
from django.db.models import Count, Avg, Sum, Case, When, IntegerField, F
from django.db.models.functions import TruncMonth, TruncWeek
from dashboards.models import MentorVisit, School
import json

def generate_visit_frequency_chart(visits, time_period='week'):
    """
    Generate chart data for visit frequency over time
    
    Args:
        visits: QuerySet of MentorVisit objects
        time_period: 'week' or 'month'
    
    Returns:
        JSON-serialized chart data
    """
    # Group visits by time period
    if time_period == 'week':
        visits_by_time = visits.annotate(
            period=TruncWeek('visit_date')
        ).values('period').annotate(count=Count('id')).order_by('period')
        
        # Format for chart display
        labels = [item['period'].strftime('%b %d') for item in visits_by_time]
    else:
        visits_by_time = visits.annotate(
            period=TruncMonth('visit_date')
        ).values('period').annotate(count=Count('id')).order_by('period')
        
        # Format for chart display
        labels = [item['period'].strftime('%b %Y') for item in visits_by_time]
    
    values = [item['count'] for item in visits_by_time]
    
    # Prepare chart data
    chart_data = {
        'labels': labels,
        'datasets': [{
            'label': 'Number of Visits',
            'data': values,
            'backgroundColor': 'rgba(54, 162, 235, 0.5)',
            'borderColor': 'rgba(54, 162, 235, 1)',
            'borderWidth': 1
        }]
    }
    
    return json.dumps(chart_data)

def generate_quality_rating_chart(visits):
    """
    Generate chart data for quality ratings distribution
    
    Args:
        visits: QuerySet of MentorVisit objects
    
    Returns:
        JSON-serialized chart data
    """
    # Count visits by quality rating
    rating_counts = visits.values('quality_rating').annotate(
        count=Count('id')
    ).order_by('quality_rating')
    
    # Format for chart display
    labels = [f"Rating {item['quality_rating']}" for item in rating_counts]
    values = [item['count'] for item in rating_counts]
    
    # Generate a color gradient from red to green
    colors = []
    for i, rating in enumerate(rating_counts):
        r = max(0, int(255 * (1 - rating['quality_rating'] / 10)))
        g = max(0, int(255 * (rating['quality_rating'] / 10)))
        b = 0
        colors.append(f'rgba({r}, {g}, {b}, 0.7)')
    
    # Prepare chart data
    chart_data = {
        'labels': labels,
        'datasets': [{
            'label': 'Number of Visits',
            'data': values,
            'backgroundColor': colors,
            'borderColor': colors,
            'borderWidth': 1
        }]
    }
    
    return json.dumps(chart_data)

def generate_tracker_accuracy_chart(visits):
    """
    Generate chart data for tracker accuracy metrics
    
    Args:
        visits: QuerySet of MentorVisit objects
    
    Returns:
        JSON-serialized chart data
    """
    # Calculate percentage of correct tracker usage
    total_visits = visits.count()
    if total_visits == 0:
        return json.dumps({})  # Return empty data if no visits
    
    metrics = {
        'Letter Trackers': visits.filter(letter_trackers_correct=True).count() / total_visits * 100,
        'Reading Trackers': visits.filter(reading_trackers_correct=True).count() / total_visits * 100,
        'Session Trackers': visits.filter(sessions_correct=True).count() / total_visits * 100,
        'Admin': visits.filter(admin_correct=True).count() / total_visits * 100
    }
    
    # Format for chart display
    labels = list(metrics.keys())
    values = list(metrics.values())
    
    # Prepare chart data for radar chart
    chart_data = {
        'labels': labels,
        'datasets': [{
            'label': 'Correct Usage (%)',
            'data': values,
            'backgroundColor': 'rgba(54, 162, 235, 0.2)',
            'borderColor': 'rgba(54, 162, 235, 1)',
            'pointBackgroundColor': 'rgba(54, 162, 235, 1)',
            'pointBorderColor': '#fff',
            'pointHoverBackgroundColor': '#fff',
            'pointHoverBorderColor': 'rgba(54, 162, 235, 1)'
        }]
    }
    
    return json.dumps(chart_data)

def generate_school_visit_map(visits):
    """
    Generate map data for school visit distribution
    
    Args:
        visits: QuerySet of MentorVisit objects
    
    Returns:
        JSON-serialized map data
    """
    # Count visits by school and get school locations
    school_visits = School.objects.filter(
        visits__in=visits
    ).annotate(
        visit_count=Count('visits'),
        avg_quality=Avg('visits__quality_rating')
    ).values(
        'id', 'name', 'latitude', 'longitude', 'type',
        'visit_count', 'avg_quality'
    )
    
    # Format for map display
    map_data = []
    for school in school_visits:
        # Skip schools without coordinates
        if not school['latitude'] or not school['longitude']:
            continue
            
        map_data.append({
            'id': school['id'],
            'name': school['name'],
            'type': school['type'] or 'Unknown',
            'latitude': float(school['latitude']),
            'longitude': float(school['longitude']),
            'visit_count': school['visit_count'],
            'avg_quality': round(school['avg_quality'], 1) if school['avg_quality'] else 'N/A'
        })
    
    return json.dumps(map_data)

def generate_dashboard_summary(visits):
    """
    Generate summary statistics for the dashboard
    
    Args:
        visits: QuerySet of MentorVisit objects
    
    Returns:
        Dictionary of summary statistics
    """
    # Get visits in the last 30 days
    thirty_days_ago = datetime.now().date() - timedelta(days=30)
    recent_visits = visits.filter(visit_date__gte=thirty_days_ago)
    
    # Calculate summary statistics
    summary = {
        'total_visits': visits.count(),
        'recent_visits': recent_visits.count(),
        'schools_visited': visits.values('school').distinct().count(),
        'avg_quality': visits.aggregate(avg=Avg('quality_rating'))['avg'],
        'tracker_accuracy': {
            'letter': visits.filter(letter_trackers_correct=True).count() / max(visits.count(), 1) * 100,
            'reading': visits.filter(reading_trackers_correct=True).count() / max(visits.count(), 1) * 100,
            'sessions': visits.filter(sessions_correct=True).count() / max(visits.count(), 1) * 100,
            'admin': visits.filter(admin_correct=True).count() / max(visits.count(), 1) * 100,
        }
    }
    
    return summary

def generate_schools_last_visited(visits):
    """
    Generate data for schools last visited component
    
    Args:
        visits: QuerySet of MentorVisit objects
    
    Returns:
        List of school visit data sorted by days since last visit (descending)
    """
    from django.db.models import Max, F
    from django.utils import timezone
    import json
    
    # Get the latest visit date for each school
    school_visits = visits.values('school__id', 'school__name', 'school__type').annotate(
        last_visit_date=Max('visit_date'),
    ).order_by('last_visit_date')
    
    # Calculate days since last visit
    today = timezone.now().date()
    result = []
    
    for school in school_visits:
        days_ago = (today - school['last_visit_date']).days
        
        result.append({
            'school_id': school['school__id'],
            'school_name': school['school__name'],
            'school_type': school['school__type'] or 'Unknown',
            'last_visit_date': school['last_visit_date'].strftime('%Y-%m-%d'),
            'days_ago': days_ago
        })
    
    return result