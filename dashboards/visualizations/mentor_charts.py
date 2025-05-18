import json
from datetime import datetime, timedelta
from django.db.models import Count, Avg, Sum, Case, When, IntegerField, F, OuterRef, Subquery
from django.db.models.functions import TruncMonth, TruncWeek
from api.models import MentorVisit, School
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
    Generate data for schools last visited component, including schools that have never been visited
    
    Args:
        visits: QuerySet of MentorVisit objects
    
    Returns:
        List of school visit data sorted by days since last visit (descending)
    """
    try:
        from django.db.models import Max, F, OuterRef, Subquery
        from django.utils import timezone
        from api.models import School
        import json
        import logging
        logger = logging.getLogger(__name__)
        
        # Log what we're doing
        logger.error(f"Starting generate_schools_last_visited with {len(visits)} visits")
        
        today = timezone.now().date()
        
        # Let's check our database tables before proceeding
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM dashboards_school")
            school_count = cursor.fetchone()[0]
            logger.error(f"Found {school_count} schools in dashboards_school table")
            
            # Also check if api_school exists
            try:
                cursor.execute("SELECT COUNT(*) FROM api_school")
                api_school_count = cursor.fetchone()[0]
                logger.error(f"Found {api_school_count} schools in api_school table")
            except:
                logger.error("Table api_school does not exist")
        
        # Try to load a few schools directly to see what we get
        try:
            direct_schools = School.objects.all()[:3]
            logger.error(f"Direct School query returned: {[s.name for s in direct_schools]}")
        except Exception as e:
            logger.error(f"Error in direct School query: {str(e)}")
        
        # FALLBACK APPROACH: Use raw SQL instead of ORM
        # This bypasses any ORM/model issues
        result = []
        
        with connection.cursor() as cursor:
            # Get schools with their last visit
            cursor.execute("""
                SELECT 
                    s.id, 
                    s.name, 
                    s.type,
                    MAX(v.visit_date) as last_visit_date,
                    CASE WHEN MAX(v.visit_date) IS NOT NULL THEN
                        (SELECT u.first_name FROM auth_user u 
                         JOIN dashboards_mentorvisit mv ON u.id = mv.mentor_id
                         WHERE mv.school_id = s.id 
                         ORDER BY mv.visit_date DESC LIMIT 1)
                    ELSE NULL END as mentor_first_name,
                    CASE WHEN MAX(v.visit_date) IS NOT NULL THEN
                        (SELECT u.last_name FROM auth_user u 
                         JOIN dashboards_mentorvisit mv ON u.id = mv.mentor_id
                         WHERE mv.school_id = s.id
                         ORDER BY mv.visit_date DESC LIMIT 1)
                    ELSE NULL END as mentor_last_name
                FROM 
                    dashboards_school s
                LEFT JOIN 
                    dashboards_mentorvisit v ON s.id = v.school_id
                GROUP BY 
                    s.id, s.name, s.type
                ORDER BY 
                    last_visit_date DESC NULLS LAST
            """)
            
            # Process the rows
            schools_data = cursor.fetchall()
            
            for row in schools_data:
                school_id, name, school_type, last_visit_date, mentor_first, mentor_last = row
                
                days_ago = 999 if last_visit_date is None else (today - last_visit_date).days
                
                # Format mentor name
                mentor_name = "None"
                if mentor_first and mentor_last:
                    mentor_name = f"{mentor_first} {mentor_last}"
                elif mentor_first:
                    mentor_name = mentor_first
                elif last_visit_date:
                    mentor_name = "Unknown"
                    
                result.append({
                    'school_id': school_id,
                    'school_name': name,
                    'school_type': school_type or 'Unknown',
                    'last_visit_date': last_visit_date.strftime('%Y-%m-%d') if last_visit_date else 'Never',
                    'days_ago': days_ago,
                    'last_mentor': mentor_name
                })
        
        # Sort by days_ago in descending order
        result.sort(key=lambda x: x['days_ago'], reverse=True)
        
        return result
        
    except Exception as e:
        # Log the error
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"ERROR in generate_schools_last_visited: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return an empty result to prevent the entire view from crashing
        return []