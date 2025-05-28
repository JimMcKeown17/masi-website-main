import json
from datetime import datetime, timedelta
from django.db.models import Count, Avg, Sum, Case, When, IntegerField, F, OuterRef, Subquery
from django.db.models.functions import TruncMonth, TruncWeek
from api.models import MentorVisit, YeboVisit, ThousandStoriesVisit, School
import json

def generate_combined_visit_frequency_chart(mentor_visits, yebo_visits, thousand_stories_visits, time_period='week'):
    """
    Generate chart data for combined visit frequency over time from all three visit types
    
    Args:
        mentor_visits: QuerySet of MentorVisit objects
        yebo_visits: QuerySet of YeboVisit objects  
        thousand_stories_visits: QuerySet of ThousandStoriesVisit objects
        time_period: 'week' or 'month'
    
    Returns:
        JSON-serialized chart data
    """
    # Combine all visits with their types
    all_periods = set()
    
    # Process each visit type
    if time_period == 'week':
        mentor_by_time = mentor_visits.annotate(period=TruncWeek('visit_date')).values('period').annotate(count=Count('id')).order_by('period')
        yebo_by_time = yebo_visits.annotate(period=TruncWeek('visit_date')).values('period').annotate(count=Count('id')).order_by('period')
        stories_by_time = thousand_stories_visits.annotate(period=TruncWeek('visit_date')).values('period').annotate(count=Count('id')).order_by('period')
        date_format = '%b %d'
    else:
        mentor_by_time = mentor_visits.annotate(period=TruncMonth('visit_date')).values('period').annotate(count=Count('id')).order_by('period')
        yebo_by_time = yebo_visits.annotate(period=TruncMonth('visit_date')).values('period').annotate(count=Count('id')).order_by('period')
        stories_by_time = thousand_stories_visits.annotate(period=TruncMonth('visit_date')).values('period').annotate(count=Count('id')).order_by('period')
        date_format = '%b %Y'
    
    # Collect all periods
    for item in mentor_by_time:
        all_periods.add(item['period'])
    for item in yebo_by_time:
        all_periods.add(item['period'])
    for item in stories_by_time:
        all_periods.add(item['period'])
    
    # Sort periods
    sorted_periods = sorted(all_periods)
    
    # Create data dictionaries for lookup
    mentor_data = {item['period']: item['count'] for item in mentor_by_time}
    yebo_data = {item['period']: item['count'] for item in yebo_by_time}
    stories_data = {item['period']: item['count'] for item in stories_by_time}
    
    # Build chart data
    labels = [period.strftime(date_format) for period in sorted_periods]
    mentor_values = [mentor_data.get(period, 0) for period in sorted_periods]
    yebo_values = [yebo_data.get(period, 0) for period in sorted_periods]
    stories_values = [stories_data.get(period, 0) for period in sorted_periods]
    
    chart_data = {
        'labels': labels,
        'datasets': [
            {
                'label': 'Masi Literacy Visits',
                'data': mentor_values,
                'backgroundColor': 'rgba(54, 162, 235, 0.5)',
                'borderColor': 'rgba(54, 162, 235, 1)',
                'borderWidth': 1
            },
            {
                'label': 'Yebo Visits',
                'data': yebo_values,
                'backgroundColor': 'rgba(255, 99, 132, 0.5)',
                'borderColor': 'rgba(255, 99, 132, 1)',
                'borderWidth': 1
            },
            {
                'label': '1000 Stories Visits',
                'data': stories_values,
                'backgroundColor': 'rgba(75, 192, 192, 0.5)',
                'borderColor': 'rgba(75, 192, 192, 1)',
                'borderWidth': 1
            }
        ]
    }
    
    return json.dumps(chart_data)

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

def generate_combined_quality_rating_chart(mentor_visits, yebo_visits, thousand_stories_visits):
    """
    Generate chart data for quality ratings distribution from all visit types
    
    Args:
        mentor_visits: QuerySet of MentorVisit objects
        yebo_visits: QuerySet of YeboVisit objects
        thousand_stories_visits: QuerySet of ThousandStoriesVisit objects
    
    Returns:
        JSON-serialized chart data
    """
    # Collect all ratings
    all_ratings = {}
    
    # Count literacy visits by quality rating
    literacy_ratings = mentor_visits.values('quality_rating').annotate(count=Count('id')).order_by('quality_rating')
    for item in literacy_ratings:
        rating = item['quality_rating']
        all_ratings[rating] = all_ratings.get(rating, {'literacy': 0, 'yebo': 0, 'stories': 0})
        all_ratings[rating]['literacy'] = item['count']
    
    # Count Yebo visits by afternoon session quality
    yebo_ratings = yebo_visits.values('afternoon_session_quality').annotate(count=Count('id')).order_by('afternoon_session_quality')
    for item in yebo_ratings:
        rating = item['afternoon_session_quality']
        all_ratings[rating] = all_ratings.get(rating, {'literacy': 0, 'yebo': 0, 'stories': 0})
        all_ratings[rating]['yebo'] = item['count']
    
    # Count 1000 Stories visits by story time quality
    stories_ratings = thousand_stories_visits.values('story_time_quality').annotate(count=Count('id')).order_by('story_time_quality')
    for item in stories_ratings:
        rating = item['story_time_quality']
        all_ratings[rating] = all_ratings.get(rating, {'literacy': 0, 'yebo': 0, 'stories': 0})
        all_ratings[rating]['stories'] = item['count']
    
    # Sort ratings
    sorted_ratings = sorted(all_ratings.keys())
    
    # Build chart data
    labels = [f"Rating {rating}" for rating in sorted_ratings]
    literacy_values = [all_ratings[rating]['literacy'] for rating in sorted_ratings]
    yebo_values = [all_ratings[rating]['yebo'] for rating in sorted_ratings]
    stories_values = [all_ratings[rating]['stories'] for rating in sorted_ratings]
    
    chart_data = {
        'labels': labels,
        'datasets': [
            {
                'label': 'Masi Literacy',
                'data': literacy_values,
                'backgroundColor': 'rgba(54, 162, 235, 0.7)',
                'borderColor': 'rgba(54, 162, 235, 1)',
                'borderWidth': 1
            },
            {
                'label': 'Yebo',
                'data': yebo_values,
                'backgroundColor': 'rgba(255, 99, 132, 0.7)',
                'borderColor': 'rgba(255, 99, 132, 1)',
                'borderWidth': 1
            },
            {
                'label': '1000 Stories',
                'data': stories_values,
                'backgroundColor': 'rgba(75, 192, 192, 0.7)',
                'borderColor': 'rgba(75, 192, 192, 1)',
                'borderWidth': 1
            }
        ]
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

def generate_letter_tracker_accuracy_chart(visits):
    """
    Generate chart data for letter tracker accuracy metrics (Literacy only)
    
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

# Keep the old function name for backward compatibility
def generate_tracker_accuracy_chart(visits):
    """Legacy function name - calls generate_letter_tracker_accuracy_chart"""
    return generate_letter_tracker_accuracy_chart(visits)

def generate_combined_school_visit_map(mentor_visits, yebo_visits, thousand_stories_visits):
    """
    Generate map data for school visit distribution from all visit types
    
    Args:
        mentor_visits: QuerySet of MentorVisit objects
        yebo_visits: QuerySet of YeboVisit objects
        thousand_stories_visits: QuerySet of ThousandStoriesVisit objects
    
    Returns:
        JSON-serialized map data
    """
    # Get schools with visit counts from all types
    schools_data = {}
    
    # Process literacy visits
    literacy_schools = School.objects.filter(visits__in=mentor_visits).annotate(
        visit_count=Count('visits'),
        avg_quality=Avg('visits__quality_rating')
    ).values('id', 'name', 'latitude', 'longitude', 'type', 'visit_count', 'avg_quality')
    
    for school in literacy_schools:
        school_id = school['id']
        schools_data[school_id] = {
            'id': school_id,
            'name': school['name'],
            'type': school['type'] or 'Unknown',
            'latitude': float(school['latitude']) if school['latitude'] else None,
            'longitude': float(school['longitude']) if school['longitude'] else None,
            'literacy_visits': school['visit_count'],
            'literacy_avg_quality': round(school['avg_quality'], 1) if school['avg_quality'] else 0,
            'yebo_visits': 0,
            'yebo_avg_quality': 0,
            'stories_visits': 0,
            'stories_avg_quality': 0
        }
    
    # Process Yebo visits
    yebo_schools = School.objects.filter(yebo_visits__in=yebo_visits).annotate(
        visit_count=Count('yebo_visits'),
        avg_quality=Avg('yebo_visits__afternoon_session_quality')
    ).values('id', 'name', 'latitude', 'longitude', 'type', 'visit_count', 'avg_quality')
    
    for school in yebo_schools:
        school_id = school['id']
        if school_id not in schools_data:
            schools_data[school_id] = {
                'id': school_id,
                'name': school['name'],
                'type': school['type'] or 'Unknown',
                'latitude': float(school['latitude']) if school['latitude'] else None,
                'longitude': float(school['longitude']) if school['longitude'] else None,
                'literacy_visits': 0,
                'literacy_avg_quality': 0,
                'yebo_visits': 0,
                'yebo_avg_quality': 0,
                'stories_visits': 0,
                'stories_avg_quality': 0
            }
        schools_data[school_id]['yebo_visits'] = school['visit_count']
        schools_data[school_id]['yebo_avg_quality'] = round(school['avg_quality'], 1) if school['avg_quality'] else 0
    
    # Process 1000 Stories visits
    stories_schools = School.objects.filter(thousand_stories_visits__in=thousand_stories_visits).annotate(
        visit_count=Count('thousand_stories_visits'),
        avg_quality=Avg('thousand_stories_visits__story_time_quality')
    ).values('id', 'name', 'latitude', 'longitude', 'type', 'visit_count', 'avg_quality')
    
    for school in stories_schools:
        school_id = school['id']
        if school_id not in schools_data:
            schools_data[school_id] = {
                'id': school_id,
                'name': school['name'],
                'type': school['type'] or 'Unknown',
                'latitude': float(school['latitude']) if school['latitude'] else None,
                'longitude': float(school['longitude']) if school['longitude'] else None,
                'literacy_visits': 0,
                'literacy_avg_quality': 0,
                'yebo_visits': 0,
                'yebo_avg_quality': 0,
                'stories_visits': 0,
                'stories_avg_quality': 0
            }
        schools_data[school_id]['stories_visits'] = school['visit_count']
        schools_data[school_id]['stories_avg_quality'] = round(school['avg_quality'], 1) if school['avg_quality'] else 0
    
    # Format for map display
    map_data = []
    for school in schools_data.values():
        # Skip schools without coordinates
        if not school['latitude'] or not school['longitude']:
            continue
        
        total_visits = school['literacy_visits'] + school['yebo_visits'] + school['stories_visits']
        
        map_data.append({
            'id': school['id'],
            'name': school['name'],
            'type': school['type'],
            'latitude': school['latitude'],
            'longitude': school['longitude'],
            'total_visits': total_visits,
            'literacy_visits': school['literacy_visits'],
            'yebo_visits': school['yebo_visits'],
            'stories_visits': school['stories_visits'],
            'literacy_avg_quality': school['literacy_avg_quality'],
            'yebo_avg_quality': school['yebo_avg_quality'],
            'stories_avg_quality': school['stories_avg_quality']
        })
    
    return json.dumps(map_data)

def generate_school_visit_map(visits):
    """
    Generate map data for school visit distribution (MentorVisit only)
    
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

def generate_yebo_school_visit_map(yebo_visits):
    """
    Generate map data for Yebo school visit distribution
    
    Args:
        yebo_visits: QuerySet of YeboVisit objects
    
    Returns:
        JSON-serialized map data
    """
    # Count visits by school and get school locations
    school_visits = School.objects.filter(
        yebo_visits__in=yebo_visits
    ).annotate(
        visit_count=Count('yebo_visits'),
        avg_quality=Avg('yebo_visits__afternoon_session_quality')
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

def generate_thousand_stories_school_visit_map(thousand_stories_visits):
    """
    Generate map data for 1000 Stories school visit distribution
    
    Args:
        thousand_stories_visits: QuerySet of ThousandStoriesVisit objects
    
    Returns:
        JSON-serialized map data
    """
    # Count visits by school and get school locations
    school_visits = School.objects.filter(
        thousand_stories_visits__in=thousand_stories_visits
    ).annotate(
        visit_count=Count('thousand_stories_visits'),
        avg_quality=Avg('thousand_stories_visits__story_time_quality')
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

def generate_combined_dashboard_summary(mentor_visits, yebo_visits, thousand_stories_visits):
    """
    Generate combined dashboard summary statistics from all three visit types
    
    Args:
        mentor_visits: QuerySet of MentorVisit objects
        yebo_visits: QuerySet of YeboVisit objects  
        thousand_stories_visits: QuerySet of ThousandStoriesVisit objects
    
    Returns:
        Dictionary containing combined summary statistics
    """
    from datetime import datetime, timedelta
    
    thirty_days_ago = datetime.now().date() - timedelta(days=30)
    
    # Individual visit counts
    literacy_total = mentor_visits.count()
    yebo_total = yebo_visits.count()
    stories_total = thousand_stories_visits.count()
    
    # Recent visit counts (last 30 days)
    literacy_recent = mentor_visits.filter(visit_date__gte=thirty_days_ago).count()
    yebo_recent = yebo_visits.filter(visit_date__gte=thirty_days_ago).count()
    stories_recent = thousand_stories_visits.filter(visit_date__gte=thirty_days_ago).count()
    
    # Combined totals
    total_visits = literacy_total + yebo_total + stories_total
    total_recent = literacy_recent + yebo_recent + stories_recent
    
    # Combined schools visited
    literacy_schools = set(mentor_visits.values_list('school_id', flat=True))
    yebo_schools = set(yebo_visits.values_list('school_id', flat=True))
    stories_schools = set(thousand_stories_visits.values_list('school_id', flat=True))
    combined_schools = literacy_schools.union(yebo_schools).union(stories_schools)
    
    # Calculate average quality ratings
    literacy_avg_quality = mentor_visits.aggregate(
        avg_quality=Avg('quality_rating')
    )['avg_quality'] or 0
    
    yebo_avg_quality = yebo_visits.aggregate(
        avg_quality=Avg('afternoon_session_quality')
    )['avg_quality'] or 0
    
    stories_avg_quality = thousand_stories_visits.aggregate(
        avg_quality=Avg('story_time_quality')
    )['avg_quality'] or 0
    
    # Calculate weighted average quality (weighted by number of visits)
    total_quality_points = (
        literacy_avg_quality * literacy_total +
        yebo_avg_quality * yebo_total +
        stories_avg_quality * stories_total
    )
    combined_avg_quality = total_quality_points / total_visits if total_visits > 0 else 0
    
    return {
        'total_visits': total_visits,
        'recent_visits': total_recent,
        'schools_visited': len(combined_schools),
        'avg_quality': combined_avg_quality,
        'literacy_visits': literacy_total,
        'literacy_recent_visits': literacy_recent,
        'yebo_visits': yebo_total,
        'yebo_recent_visits': yebo_recent,
        'stories_visits': stories_total,
        'stories_recent_visits': stories_recent,
    }

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
            cursor.execute("SELECT COUNT(*) FROM api_school")
            school_count = cursor.fetchone()[0]
            logger.error(f"Found {school_count} schools in api_school table")
            
            # Also check if api_mentorvisit exists
            try:
                cursor.execute("SELECT COUNT(*) FROM api_mentorvisit")
                mentorvisit_count = cursor.fetchone()[0]
                logger.error(f"Found {mentorvisit_count} visits in api_mentorvisit table")
            except Exception as e:
                logger.error(f"Error checking api_mentorvisit table: {str(e)}")
        
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
                         JOIN api_mentorvisit mv ON u.id = mv.mentor_id
                         WHERE mv.school_id = s.id 
                         ORDER BY mv.visit_date DESC LIMIT 1)
                    ELSE NULL END as mentor_first_name,
                    CASE WHEN MAX(v.visit_date) IS NOT NULL THEN
                        (SELECT u.last_name FROM auth_user u 
                         JOIN api_mentorvisit mv ON u.id = mv.mentor_id
                         WHERE mv.school_id = s.id
                         ORDER BY mv.visit_date DESC LIMIT 1)
                    ELSE NULL END as mentor_last_name
                FROM 
                    api_school s
                LEFT JOIN 
                    api_mentorvisit v ON s.id = v.school_id
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

def get_recent_literacy_submissions(mentor_visits, limit=50):
    """
    Get recent literacy visit submissions
    
    Args:
        mentor_visits: QuerySet of MentorVisit objects
        limit: Maximum number of submissions to return
    
    Returns:
        QuerySet of recent MentorVisit submissions
    """
    return mentor_visits.select_related('mentor', 'school').order_by('-created_at')[:limit]

def get_recent_yebo_submissions(yebo_visits, limit=50):
    """
    Get recent Yebo visit submissions
    
    Args:
        yebo_visits: QuerySet of YeboVisit objects
        limit: Maximum number of submissions to return
    
    Returns:
        QuerySet of recent YeboVisit submissions
    """
    return yebo_visits.select_related('mentor', 'school').order_by('-created_at')[:limit]

def get_recent_thousand_stories_submissions(thousand_stories_visits, limit=50):
    """
    Get recent 1000 Stories visit submissions
    
    Args:
        thousand_stories_visits: QuerySet of ThousandStoriesVisit objects
        limit: Maximum number of submissions to return
    
    Returns:
        QuerySet of recent ThousandStoriesVisit submissions
    """
    return thousand_stories_visits.select_related('mentor', 'school').order_by('-created_at')[:limit]

def generate_yebo_quality_rating_chart(yebo_visits):
    """
    Generate chart data for Yebo afternoon session quality ratings distribution
    
    Args:
        yebo_visits: QuerySet of YeboVisit objects
    
    Returns:
        JSON-serialized chart data
    """
    # Count visits by afternoon session quality rating
    rating_counts = yebo_visits.values('afternoon_session_quality').annotate(
        count=Count('id')
    ).order_by('afternoon_session_quality')
    
    # Format for chart display
    labels = [f"Rating {item['afternoon_session_quality']}" for item in rating_counts]
    values = [item['count'] for item in rating_counts]
    
    # Generate a color gradient from red to green
    colors = []
    for i, rating in enumerate(rating_counts):
        r = max(0, int(255 * (1 - rating['afternoon_session_quality'] / 10)))
        g = max(0, int(255 * (rating['afternoon_session_quality'] / 10)))
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

def generate_thousand_stories_quality_rating_chart(thousand_stories_visits):
    """
    Generate chart data for 1000 Stories story time quality ratings distribution
    
    Args:
        thousand_stories_visits: QuerySet of ThousandStoriesVisit objects
    
    Returns:
        JSON-serialized chart data
    """
    # Count visits by story time quality rating
    rating_counts = thousand_stories_visits.values('story_time_quality').annotate(
        count=Count('id')
    ).order_by('story_time_quality')
    
    # Format for chart display
    labels = [f"Rating {item['story_time_quality']}" for item in rating_counts]
    values = [item['count'] for item in rating_counts]
    
    # Generate a color gradient from red to green
    colors = []
    for i, rating in enumerate(rating_counts):
        r = max(0, int(255 * (1 - rating['story_time_quality'] / 10)))
        g = max(0, int(255 * (rating['story_time_quality'] / 10)))
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